import json
import pathlib
import pytest
from urllib.parse import ParseResult, urlunparse

import tornado

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
def contents_dir(tmp_path, serverapp):
    return tmp_path / serverapp.root_dir


@pytest.fixture
def contents(contents_dir):
    for d, name in dirs:
        p = contents_dir / d
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
@pytest.mark.parametrize('path,name', dirs)
async def test_list_notebooks(fetch, contents, path, name):
    response = await fetch(
        'api', 'contents', path,
        method='GET',
    )
    data = json.loads(response.body)
    nbs = notebooks_only(data)
    assert len(nbs) > 0
    assert name+'.ipynb' in [n['name'] for n in nbs]
    assert url_path_join(path, name+'.ipynb') in [n['path'] for n in nbs]


@pytest.mark.gen_test
@pytest.mark.parametrize('path,name', dirs)
async def test_get_dir_no_contents(fetch, contents, path, name):
    response = await fetch(
        'api', 'contents', path,
        method='GET',
        params=dict(
            content='0',
        )
    )
    model = json.loads(response.body)
    assert model['path'] == path
    assert model['type'] == 'directory'
    assert 'content' in model
    assert model['content'] == None


@pytest.mark.gen_test
async def test_list_nonexistant_dir(fetch, contents):
    with pytest.raises(tornado.httpclient.HTTPClientError):
        await fetch(
            'api', 'contents', 'nonexistant',
            method='GET',
        )


@pytest.mark.gen_test
@pytest.mark.parametrize('path,name', dirs)
async def test_get_nb_contents(fetch, contents, path, name):
    nbname = name+'.ipynb'
    nbpath = (path + '/' + nbname).lstrip('/')
    r = await fetch(
        'api', 'contents', nbpath,
        method='GET',
        params=dict(content='1') 
    )
    model = json.loads(r.body)
    assert model['name'] == nbname
    assert model['path'] == nbpath
    assert model['type'] == 'notebook'
    assert 'content' in model
    assert model['format'] == 'json'
    assert 'metadata' in model['content']
    assert isinstance(model['content']['metadata'], dict)


@pytest.mark.gen_test
@pytest.mark.parametrize('path,name', dirs)
async def test_get_nb_no_contents(fetch, contents, path, name):
    nbname = name+'.ipynb'
    nbpath = (path + '/' + nbname).lstrip('/')
    r = await fetch(
        'api', 'contents', nbpath,
        method='GET',
        params=dict(content='0') 
    )
    model = json.loads(r.body)
    assert model['name'] == nbname
    assert model['path'] == nbpath
    assert model['type'] == 'notebook'
    assert 'content' in model
    assert model['content'] == None


@pytest.mark.gen_test
async def test_get_nb_invalid(contents_dir, fetch, contents):
    nb = {
        'nbformat': 4,
        'metadata': {},
        'cells': [{
            'cell_type': 'wrong',
            'metadata': {},
        }],
    }
    nbpath = u'å b/Validate tést.ipynb'
    (contents_dir / nbpath).write_text(json.dumps(nb))
    r = await fetch(
        'api', 'contents', nbpath,
        method='GET',
    )
    model = json.loads(r.body)
    assert model['path'] == nbpath
    assert model['type'] == 'notebook'
    assert 'content' in model
    assert 'message' in model
    assert 'validation failed' in model['message'].lower()


@pytest.mark.gen_test
async def test_get_contents_no_such_file(fetch):
    with pytest.raises(tornado.httpclient.HTTPClientError):
        await fetch(
            'api', 'contents', 'foo/q.ipynb',
            method='GET',
        )


@pytest.mark.gen_test
@pytest.mark.parametrize('path,name', dirs)
async def test_get_text_file_contents(fetch, contents, path, name):
    txtname = name+'.txt'
    txtpath = (path + '/' + txtname).lstrip('/')
    r = await fetch(
        'api', 'contents', txtpath,
        method='GET',
        params=dict(content='0') 
    )
    model = json.loads(r.body)
    assert model['name'] == txtname
    assert model['path'] == txtpath
    assert 'content' in model
    assert model['format'] == 'text'
    assert model['type'] == 'file'
    assert model['content'] == '{} text file'.format(name)

    with pytest.raises(tornado.httpclient.HTTPClientError):
        await fetch(
            'api', 'contents', 'foo/q.txt',
            method='GET',
        )

    with pytest.raises(tornado.httpclient.HTTPClientError):
        await fetch(
            'api', 'contents', 'foo/bar/baz.blob',
            method='GET',
            params=dict(
                type='file',
                format='text'
            )
        )


