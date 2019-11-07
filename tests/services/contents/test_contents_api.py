import json
import pathlib
import pytest

from tornado.escape import url_escape

from nbformat import writes, from_dict
from nbformat.v4 import (
    new_notebook, new_markdown_cell,
)

from jupyter_server.utils import url_path_join


def notebooks_only(dir_model):
    return [nb for nb in dir_model['content'] if nb['type']=='notebook']

def dirs_only(dir_model):
    return [x for x in dir_model['content'] if x['type']=='directory']


dirs = [
    ('', 'inroot'),
    ('Directory with spaces in', 'inspace'),
    (u'unicodé', 'innonascii'),
    ('foo', 'a'),
    ('foo', 'b'),
    ('foo', 'name with spaces'),
    ('foo', u'unicodé'),
    ('foo/bar', 'baz'),
    ('ordering', 'A'),
    ('ordering', 'b'),
    ('ordering', 'C'),
    (u'å b', u'ç d'),
]


@pytest.fixture
def contents(tmp_path, serverapp):
    for d, name in dirs:
        p = tmp_path / serverapp.root_dir / d
        p.mkdir(parents=True, exist_ok=True)

        # Create a notebook
        nb = writes(new_notebook(), version=4)
        nbname = p.joinpath('{}.ipynb'.format(name))
        nbname.write_text(nb)

        # Create a text file
        txt = '{} text file'.format(name)
        txtname = p.joinpath('{}.txt'.format(name))
        txtname.write_text(txt)

        # Create a random blob
        blob = name.encode('utf-8') + b'\xFF'
        blobname = p.joinpath('{}.blob'.format(name))
        blobname.write_bytes(blob)


@pytest.mark.gen_test
@pytest.mark.parametrize(
    'path,name',
    dirs
)
def test_list_notebooks(fetch, contents, path, name):
    url_path = url_escape(path, plus=False)
    response = yield fetch(
        'api', 'contents', url_path,
        method='GET',
    )
    data = json.loads(response.body)
    nbs = notebooks_only(data)
    assert len(nbs) > 0
    assert name+'.ipynb' in [n['name'] for n in nbs]
    assert url_path_join(path, name+'.ipynb') in [n['path'] for n in nbs]

