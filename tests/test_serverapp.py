import pytest
import logging

from traitlets import TraitError
from traitlets.tests.utils import check_help_all_output

from jupyter_server.serverapp import ServerApp, list_running_servers


def test_help_output():
    """jupyter server --help-all works"""
    check_help_all_output('jupyter_server')


def test_server_info_file(tmp_path):
    app = ServerApp(runtime_dir=str(tmp_path), log=logging.getLogger())

    app.initialize(argv=[])
    app.write_server_info_file()
    servers = list(list_running_servers(app.runtime_dir))

    assert len(servers) == 1
    sinfo = servers[0]    
    
    assert sinfo['port'] == app.port
    assert sinfo['url'] == app.connection_url
    assert sinfo['version'] == app.version
    
    app.remove_server_info_file()

    assert list(list_running_servers(app.runtime_dir)) == []
    app.remove_server_info_file


def test_root_dir(tmp_path):
    app = ServerApp(root_dir=str(tmp_path))
    assert app.root_dir == str(tmp_path)


def test_no_create_root_dir(tmp_path):
    root_dir = tmp_path / 'notebooks'
    app = ServerApp()
    with pytest.raises(TraitError):
        app.root_dir = root_dir
