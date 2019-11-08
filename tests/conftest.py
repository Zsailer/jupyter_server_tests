import os
import pytest
import asyncio
from binascii import hexlify

import urllib.parse
from tornado.escape import url_escape

from traitlets.config import Config

from jupyter_server.serverapp import ServerApp
from jupyter_server.utils import url_path_join


pytest_plugins = ("pytest_asyncio", "pytest_tornado")


@pytest.fixture
def serverapp(tmp_path, http_port):
    def tmp(*parts):
        path = tmp_path.joinpath(*parts)
        if not path.exists():
            path.mkdir(parents=True)
        return str(path)

    home_dir = tmp('home')
    data_dir = tmp('data')
    config_dir = tmp('config')
    runtime_dir = tmp('runtime')
    root_dir = tmp('root_dir')

    config = Config()
    config.NotebookNotary.db_file = ':memory:'

    token = hexlify(os.urandom(4)).decode('ascii')

    url_prefix = '/'

    app = ServerApp(
        port=http_port,
        port_retries=0,
        open_browser=False,
        config_dir=config_dir,
        data_dir=data_dir,
        runtime_dir=runtime_dir,
        root_dir=root_dir,
        base_url=url_prefix,
        config=config,
        allow_root=True,
        token=token,
    )
    app.init_signal = lambda : None
    app.log.propagate = True
    app.log.handlers = []
    # Initialize app without httpserver
    app.initialize(argv=[], new_httpserver=False)
    app.log.propagate = True
    app.log.handlers = []
    # Start app without ioloop
    app.start_app()
    return app


@pytest.fixture
def event_loop(io_loop):
    """Enforce that asyncio and tornado use the same event loop."""
    loop = io_loop.current().asyncio_loop
    yield loop
    loop.stop()


@pytest.fixture
def app(serverapp):
    return serverapp.web_app


@pytest.fixture
def auth_header(serverapp):
    return {'Authorization': 'token {token}'.format(token=serverapp.token)}


@pytest.fixture
def fetch(http_client, auth_header, base_url):
    """fetch fixture that handles auth, base_url, and path"""
    def client_fetch(*parts, headers={}, params={}, **kwargs):
        # Handle URL strings
        path = url_escape(url_path_join(*parts), plus=False)
        urlparts = urllib.parse.urlparse(base_url)
        urlparts = urlparts._replace(
            path=path,
            query=urllib.parse.urlencode(params),
        )
        url = urlparts.geturl()
        # Add auth keys to header
        headers.update(auth_header)
        # Make request.
        print(url)
        return http_client.fetch(url, headers=headers, **kwargs)
    return client_fetch