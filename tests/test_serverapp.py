
import os
import getpass
import pathlib
import pytest
import logging

from unittest.mock import patch


from traitlets import TraitError
from traitlets.tests.utils import check_help_all_output

from jupyter_core.application import NoStart


from jupyter_server.serverapp import (
    ServerApp, 
    list_running_servers,
    JupyterPasswordApp
)
from jupyter_server.auth.security import passwd_check


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
        app.root_dir = str(root_dir)


def test_missing_root_dir(tmp_path):
    root_dir = tmp_path.joinpath(tmp_path, 'root', 'dir', 'is', 'missing')
    app = ServerApp()
    with pytest.raises(TraitError):
        app.root_dir = str(root_dir)


def test_invalid_root_dir(tmp_path):
    file_name = tmp_path / 'test.txt'
    file_name.write_text('')
    app = ServerApp()
    with pytest.raises(TraitError):
        app.root_dir = str(file_name)


def test_root_dir_with_slash(tmp_path):
    root_dir = tmp_path / ''
    app = ServerApp(root_dir=str(root_dir))
    assert app.root_dir.endswith(os.sep) is False


def test_root_dir_root():
    root = pathlib.Path(os.sep).root
    app = ServerApp(root_dir=str(root))
    assert app.root_dir == str(root)


def test_generate_config(tmp_path):
    app = ServerApp(config_dir=str(tmp_path))
    app.initialize(['--generate-config', '--allow-root'])
    with pytest.raises(NoStart):
        app.start()
    assert tmp_path.joinpath('jupyter_server_config.py').exists()


def test_server_password(tmp_path):
    password = 'secret'
    with patch.dict('os.environ', {'JUPYTER_CONFIG_DIR': str(tmp_path)}), patch.object(getpass, 'getpass', return_value=password):
        app = JupyterPasswordApp(log_level=logging.ERROR)
        app.initialize([])
        app.start()
        sv = ServerApp()
        sv.load_config_file()
        assert sv.password != ''
        passwd_check(sv.password, password)