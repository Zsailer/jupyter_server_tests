import os
import sys
import pytest
import functools
import decorator
from traitlets import TraitError
from tornado.web import HTTPError

from jupyter_server.services.contents.filemanager import FileContentsManager
from ...conftest import expected_http_error

def _make_dir(contents_manager, api_path):
    """
    Make a directory.
    """
    os_path = contents_manager._get_os_path(api_path)
    try:
        os.makedirs(os_path)
    except OSError:
        print("Directory already exists: %r" % os_path)


def symlink(contents_manager, src, dst):
    """Make a symlink to src from dst

    src and dst are api_paths
    """
    src_os_path = contents_manager._get_os_path(src)
    dst_os_path = contents_manager._get_os_path(dst)
    print(src_os_path, dst_os_path, os.path.isfile(src_os_path))
    os.symlink(src_os_path, dst_os_path)


def test_root_dir(tmp_path):
    fm = FileContentsManager(root_dir=str(tmp_path))
    assert fm.root_dir == str(tmp_path)


def test_missing_root_dir(tmp_path):
    root = tmp_path / 'notebook' / 'dir' / 'is' / 'missing'
    with pytest.raises(TraitError):
        FileContentsManager(root_dir=str(root))


def test_invalid_root_dir(tmp_path):
    temp_file = tmp_path / 'file.txt'
    temp_file.write_text('')
    with pytest.raises(TraitError):
        FileContentsManager(root_dir=str(temp_file))

def test_get_os_path(tmp_path):
    fm = FileContentsManager(root_dir=str(tmp_path))
    path = fm._get_os_path('/path/to/notebook/test.ipynb')
    rel_path_list =  '/path/to/notebook/test.ipynb'.split('/')
    fs_path = os.path.join(fm.root_dir, *rel_path_list)
    assert path == fs_path

    fm = FileContentsManager(root_dir=str(tmp_path))
    path = fm._get_os_path('test.ipynb')
    fs_path = os.path.join(fm.root_dir, 'test.ipynb')
    assert path == fs_path

    fm = FileContentsManager(root_dir=str(tmp_path))
    path = fm._get_os_path('////test.ipynb')
    fs_path = os.path.join(fm.root_dir, 'test.ipynb')
    assert path == fs_path


def test_checkpoint_subdir(tmp_path):
    subd = 'sub ∂ir'
    cp_name = 'test-cp.ipynb'
    fm = FileContentsManager(root_dir=str(tmp_path))
    tmp_path.joinpath(subd).mkdir()
    cpm = fm.checkpoints
    cp_dir = cpm.checkpoint_path('cp', 'test.ipynb')
    cp_subdir = cpm.checkpoint_path('cp', '/%s/test.ipynb' % subd)
    assert cp_dir != cp_subdir
    assert cp_dir == os.path.join(str(tmp_path), cpm.checkpoint_dir, cp_name)


@pytest.mark.skipif(
    sys.platform == 'win32' and sys.version_info[0] < 3, 
    reason="System platform is Windows, version < 3"
)
def test_bad_symlink(tmp_path):
    td = str(tmp_path)

    cm = FileContentsManager(root_dir=td)
    path = 'test bad symlink'
    _make_dir(cm, path)

    file_model = cm.new_untitled(path=path, ext='.txt')

    # create a broken symlink
    symlink(cm, "target", '%s/%s' % (path, 'bad symlink'))
    model = cm.get(path)

    contents = {
        content['name']: content for content in model['content']
    }
    assert 'untitled.txt' in contents
    assert contents['untitled.txt'] == file_model
    assert 'bad symlink' in contents


@pytest.mark.skipif(
    sys.platform == 'win32' and sys.version_info[0] < 3, 
    reason="System platform is Windows, version < 3"
)
def test_good_symlink(tmp_path):
    td = str(tmp_path)
    cm = FileContentsManager(root_dir=td)
    parent = 'test good symlink'
    name = 'good symlink'
    path = '{0}/{1}'.format(parent, name)
    _make_dir(cm, parent)

    file_model = cm.new(path=parent + '/zfoo.txt')

    # create a good symlink
    symlink(cm, file_model['path'], path)
    symlink_model = cm.get(path, content=False)
    dir_model = cm.get(parent)
    assert sorted(dir_model['content'], key=lambda x: x['name']) == [symlink_model, file_model]


def test_403(tmp_path):
    if hasattr(os, 'getuid'):
        if os.getuid() == 0:
            raise pytest.skip("Can't test permissions as root")
    if sys.platform.startswith('win'):
        raise pytest.skip("Can't test permissions on Windows")

    td = str(tmp_path)
    cm = FileContentsManager(root_dir=td)
    model = cm.new_untitled(type='file')
    os_path = cm._get_os_path(model['path'])

    os.chmod(os_path, 0o400)
    try:
        with cm.open(os_path, 'w') as f:
            f.write(u"don't care")
    except HTTPError as e:
        assert e.status_code == 403

def test_escape_root(tmp_path):
    td = str(tmp_path)
    cm = FileContentsManager(root_dir=td)
    # make foo, bar next to root
    with open(os.path.join(cm.root_dir, '..', 'foo'), 'w') as f:
        f.write('foo')
    with open(os.path.join(cm.root_dir, '..', 'bar'), 'w') as f:
        f.write('bar')

    with pytest.raises(HTTPError) as e:
        cm.get('..')
    expected_http_error(e, 404)

    with pytest.raises(HTTPError) as e:
        cm.get('foo/../../../bar')
    expected_http_error(e, 404)

    with pytest.raises(HTTPError) as e:
        cm.delete('../foo')
    expected_http_error(e, 404)

    with pytest.raises(HTTPError) as e:
        cm.rename('../foo', '../bar')
    expected_http_error(e, 404)

    with pytest.raises(HTTPError) as e:
        cm.save(model={
            'type': 'file',
            'content': u'',
            'format': 'text',
        }, path='../foo')
    expected_http_error(e, 404)


contents_manager = pytest.fixture(lambda tmp_path: FileContentsManager(root_dir=str(tmp_path)))


# @pytest.mark.parametrize(
#     'type,name,path',
#     [
#         ('notebook', 'Untitled.ipynb', 'Untitled.ipynb'),
#         ('directory', 'Untitled Folder', 'Untitled Folder'),
#         ('directory')
#     ]
# )
def test_new_untitled(contents_manager):#, type, name, path):
    cm = contents_manager
    # Test in root directory
    model = cm.new_untitled(type='notebook')
    assert isinstance(model, dict)
    assert 'name' in model
    assert 'path' in model
    assert 'type' in model
    assert model['type'] == 'notebook'
    assert model['name'] == 'Untitled.ipynb'
    assert model['path'] == 'Untitled.ipynb'

    # Test in sub-directory
    model = cm.new_untitled(type='directory')
    assert isinstance(model, dict)
    assert 'name' in model
    assert 'path' in model
    assert 'type' in model
    assert model['type'] == 'directory'
    assert model['name'] == 'Untitled Folder'
    assert model['path'] == 'Untitled Folder'
    sub_dir = model['path']

    model = cm.new_untitled(path=sub_dir)
    assert isinstance(model, dict)
    assert 'name' in model
    assert 'path' in model
    assert 'type' in model
    assert model['type'] == 'file'
    assert model['name'] == 'untitled'
    assert model['path'] == '%s/untitled' % sub_dir

    # Test with a compound extension
    model = cm.new_untitled(path=sub_dir, ext='.foo.bar')
    assert model['name'] == 'untitled.foo.bar'
    model = cm.new_untitled(path=sub_dir, ext='.foo.bar')
    assert model['name'] == 'untitled1.foo.bar'
