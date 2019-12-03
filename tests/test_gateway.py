"""Test GatewayClient"""
import json
import os
import pytest
import tornado
import uuid
from datetime import datetime
from tornado import gen
from tornado.httpclient import HTTPRequest, HTTPResponse, HTTPError
from ipython_genutils.py3compat import str_to_unicode
from jupyter_server.serverapp import ServerApp

from unittest.mock import patch
from io import StringIO
from .conftest import expected_http_error

# Run all tests in this module using asyncio's event loop
pytestmark = pytest.mark.asyncio


def generate_kernelspec(name):
    argv_stanza = ['python', '-m', 'ipykernel_launcher', '-f', '{connection_file}']
    spec_stanza = {'spec': {'argv': argv_stanza, 'env': {}, 'display_name': name, 'language': 'python', 'interrupt_mode': 'signal', 'metadata': {}}}
    kernelspec_stanza = {'name': name, 'spec': spec_stanza, 'resources': {}}
    return kernelspec_stanza


# We'll mock up two kernelspecs - kspec_foo and kspec_bar
kernelspecs = {'default': 'kspec_foo', 'kernelspecs': {'kspec_foo': generate_kernelspec('kspec_foo'), 'kspec_bar': generate_kernelspec('kspec_bar')}}


# maintain a dictionary of expected running kernels.  Key = kernel_id, Value = model.
running_kernels = dict()


def generate_model(name):
    """Generate a mocked kernel model.  Caller is responsible for adding model to running_kernels dictionary."""
    dt = datetime.utcnow().isoformat() + 'Z'
    kernel_id = str(uuid.uuid4())
    model = {'id': kernel_id, 'name': name, 'last_activity': str(dt), 'execution_state': 'idle', 'connections': 1}
    return model


async def mock_gateway_request(url, **kwargs):
    method = 'GET'
    if kwargs['method']:
        method = kwargs['method']

    request = HTTPRequest(url=url, **kwargs)

    endpoint = str(url)

    # Fetch all kernelspecs
    if endpoint.endswith('/api/kernelspecs') and method == 'GET':
        response_buf = StringIO(str_to_unicode(json.dumps(kernelspecs)))
        response = await gen.maybe_future(HTTPResponse(request, 200, buffer=response_buf))
        return response

    # Fetch named kernelspec
    if endpoint.rfind('/api/kernelspecs/') >= 0 and method == 'GET':
        requested_kernelspec = endpoint.rpartition('/')[2]
        kspecs = kernelspecs.get('kernelspecs')
        if requested_kernelspec in kspecs:
            response_buf = StringIO(str_to_unicode(json.dumps(kspecs.get(requested_kernelspec))))
            response = await gen.maybe_future(HTTPResponse(request, 200, buffer=response_buf))
            return response
        else:
            raise HTTPError(404, message='Kernelspec does not exist: %s' % requested_kernelspec)

    # Create kernel
    if endpoint.endswith('/api/kernels') and method == 'POST':
        json_body = json.loads(kwargs['body'])
        name = json_body.get('name')
        env = json_body.get('env')
        kspec_name = env.get('KERNEL_KSPEC_NAME')
        assert name == kspec_name   # Ensure that KERNEL_ env values get propagated
        model = generate_model(name)
        running_kernels[model.get('id')] = model  # Register model as a running kernel
        response_buf = StringIO(str_to_unicode(json.dumps(model)))
        response = await gen.maybe_future(HTTPResponse(request, 201, buffer=response_buf))
        return response

    # Fetch list of running kernels
    if endpoint.endswith('/api/kernels') and method == 'GET':
        kernels = []
        for kernel_id in running_kernels.keys():
            model = running_kernels.get(kernel_id)
            kernels.append(model)
        response_buf = StringIO(str_to_unicode(json.dumps(kernels)))
        response = await gen.maybe_future(HTTPResponse(request, 200, buffer=response_buf))
        return response

    # Interrupt or restart existing kernel
    if endpoint.rfind('/api/kernels/') >= 0 and method == 'POST':
        requested_kernel_id, sep, action = endpoint.rpartition('/api/kernels/')[2].rpartition('/')

        if action == 'interrupt':
            if requested_kernel_id in running_kernels:
                response = await gen.maybe_future(HTTPResponse(request, 204))
                return response
            else:
                raise HTTPError(404, message='Kernel does not exist: %s' % requested_kernel_id)
        elif action == 'restart':
            if requested_kernel_id in running_kernels:
                response_buf = StringIO(str_to_unicode(json.dumps(running_kernels.get(requested_kernel_id))))
                response = await gen.maybe_future(HTTPResponse(request, 204, buffer=response_buf))
                return response
            else:
                raise HTTPError(404, message='Kernel does not exist: %s' % requested_kernel_id)
        else:
            raise HTTPError(404, message='Bad action detected: %s' % action)

    # Shutdown existing kernel
    if endpoint.rfind('/api/kernels/') >= 0 and method == 'DELETE':
        requested_kernel_id = endpoint.rpartition('/')[2]
        running_kernels.pop(requested_kernel_id)  # Simulate shutdown by removing kernel from running set
        response = await gen.maybe_future(HTTPResponse(request, 204))
        return response

    # Fetch existing kernel
    if endpoint.rfind('/api/kernels/') >= 0 and method == 'GET':
        requested_kernel_id = endpoint.rpartition('/')[2]
        if requested_kernel_id in running_kernels:
            response_buf = StringIO(str_to_unicode(json.dumps(running_kernels.get(requested_kernel_id))))
            response = await gen.maybe_future(HTTPResponse(request, 200, buffer=response_buf))
            return response
        else:
            raise HTTPError(404, message='Kernel does not exist: %s' % requested_kernel_id)


mocked_gateway = patch('jupyter_server.gateway.managers.gateway_request', mock_gateway_request)
mock_gateway_url = 'http://mock-gateway-server:8889'
mock_http_user = 'alice'


    #
    # @classmethod
    # def setup_class(cls):
    #     GatewayClient.clear_instance()
    #     super(TestGateway, cls).setup_class()
    #
    # @classmethod
    # def teardown_class(cls):
    #     GatewayClient.clear_instance()
    #     super(TestGateway, cls).teardown_class()
    #
    # @classmethod
    # def get_patch_env(cls):
    #     test_env = super(TestGateway, cls).get_patch_env()
    #     test_env.update({'JUPYTER_GATEWAY_URL': TestGateway.mock_gateway_url,
    #                      'JUPYTER_GATEWAY_REQUEST_TIMEOUT': '44.4'})
    #     return test_env
    #
    # @classmethod
    # def get_argv(cls):
    #     argv = super(TestGateway, cls).get_argv()
    #     argv.extend(['--GatewayClient.connect_timeout=44.4', '--GatewayClient.http_user=' + TestGateway.mock_http_user])
    #     return argv


@pytest.fixture
def gateway_env(monkeypatch):
    monkeypatch.setenv('JUPYTER_GATEWAY_URL', mock_gateway_url)
    monkeypatch.setenv('JUPYTER_GATEWAY_HTTP_USER', mock_http_user)
    monkeypatch.setenv('JUPYTER_GATEWAY_REQUEST_TIMEOUT', '44.4')
    monkeypatch.setenv('JUPYTER_GATEWAY_CONNECT_TIMEOUT', '44.4')


async def test_gateway_cli_options():
    app = ServerApp()
    app.initialize(["--gateway-url='" + mock_gateway_url + "'",
                    "--GatewayClient.http_user='" + mock_http_user + "'",
                    '--GatewayClient.connect_timeout=44.4',
                    '--GatewayClient.request_timeout=44.4'])

    assert app.gateway_config.gateway_enabled is True
    assert app.gateway_config.url == mock_gateway_url
    assert app.gateway_config.http_user == mock_http_user
    assert app.gateway_config.connect_timeout == app.gateway_config.request_timeout
    assert app.gateway_config.connect_timeout == 44.4


async def test_gateway_env_options(gateway_env, serverapp):
    assert serverapp.gateway_config.gateway_enabled is True
    assert serverapp.gateway_config.url == mock_gateway_url
    assert serverapp.gateway_config.http_user == mock_http_user
    assert serverapp.gateway_config.connect_timeout == serverapp.gateway_config.request_timeout
    assert serverapp.gateway_config.connect_timeout == 44.4


async def test_gateway_class_mappings(gateway_env, serverapp):
    # Ensure appropriate class mappings are in place.
    assert serverapp.kernel_manager_class.__name__ == 'GatewayKernelManager'
    assert serverapp.session_manager_class.__name__ == 'GatewaySessionManager'
    assert serverapp.kernel_spec_manager_class.__name__ == 'GatewayKernelSpecManager'


async def test_gateway_get_kernelspecs(fetch):
    # Validate that kernelspecs come from gateway.
    with mocked_gateway:
        r = await fetch(
            'api', 'kernelspecs',
            method='GET'
        )
        assert r.code == 200
        content = json.loads(r.body.decode('utf-8'), encoding='utf-8')
        kspecs = content.get('kernelspecs')
        assert len(kspecs) == 2
        assert kspecs.get('kspec_bar').get('name') == 'kspec_bar'


async def test_gateway_get_named_kernelspec(fetch):
    # Validate that a specific kernelspec can be retrieved from gateway (and an invalid spec can't)
    with mocked_gateway:
        r = await fetch(
            'api', 'kernelspecs', 'kspec_foo',
            method='GET'
        )
        assert r.code == 200
        kspec_foo = json.loads(r.body.decode('utf-8'), encoding='utf-8')
        assert kspec_foo.get('name') == 'kspec_foo'

        with pytest.raises(tornado.httpclient.HTTPClientError) as e:
            await fetch(
                'api', 'kernelspecs', 'no_such_spec',
                method='GET'
            )
        assert expected_http_error(e, 404)


async def test_gateway_session_lifecycle(root_dir, fetch):
    # Validate session lifecycle functions; create and delete.

    # create
    session_id, kernel_id = await create_session(root_dir, fetch, 'kspec_foo')

    # ensure kernel still considered running
    assert await is_kernel_running(fetch, kernel_id) is True

    # interrupt
    await interrupt_kernel(fetch, kernel_id)

    # ensure kernel still considered running
    assert await is_kernel_running(fetch, kernel_id) is True

    # restart
    await restart_kernel(fetch, kernel_id)

    # ensure kernel still considered running
    assert await is_kernel_running(fetch, kernel_id) is True

    # delete
    await delete_session(fetch, session_id)
    assert await is_kernel_running(fetch, kernel_id) is False


async def test_gateway_kernel_lifecycle(fetch):
    # Validate kernel lifecycle functions; create, interrupt, restart and delete.

    # create
    kernel_id = await create_kernel(fetch, 'kspec_bar')

    # ensure kernel still considered running
    assert await is_kernel_running(fetch, kernel_id) is True

    # interrupt
    await interrupt_kernel(fetch, kernel_id)

    # ensure kernel still considered running
    assert await is_kernel_running(fetch, kernel_id) is True

    # restart
    await restart_kernel(fetch, kernel_id)

    # ensure kernel still considered running
    assert await is_kernel_running(fetch, kernel_id) is True

    # delete
    await delete_kernel(fetch, kernel_id)
    assert await is_kernel_running(fetch, kernel_id) is False


#
# Test methods below...
#
async def create_session(root_dir, fetch, kernel_name):
    """Creates a session for a kernel.  The session is created against the server
       which then uses the gateway for kernel management.
    """
    with mocked_gateway:
        nb_path = root_dir / 'testgw.ipynb'
        body = json.dumps({'path': str(nb_path),
                           'type': 'notebook',
                           'kernel': {'name': kernel_name}})

        # add a KERNEL_ value to the current env and we'll ensure that that value exists in the mocked method
        os.environ['KERNEL_KSPEC_NAME'] = kernel_name

        # Create the kernel... (also tests get_kernel)
        r = await fetch(
            'api', 'sessions',
            method='POST',
            body=body
        )
        assert r.code == 201
        model = json.loads(r.body.decode('utf-8'), encoding='utf-8')
        assert model.get('path') == str(nb_path)
        kernel_id = model.get('kernel').get('id')
        # ensure its in the running_kernels and name matches.
        running_kernel = running_kernels.get(kernel_id)
        assert kernel_id == running_kernel.get('id')
        assert model.get('kernel').get('name') == running_kernel.get('name')
        session_id = model.get('id')

        # restore env
        os.environ.pop('KERNEL_KSPEC_NAME')
        return session_id, kernel_id


async def delete_session(fetch, session_id):
    """Deletes a session corresponding to the given session id.
    """
    with mocked_gateway:
        # Delete the session (and kernel)
        r = await fetch(
            'api', 'sessions', session_id,
            method='DELETE'
        )
        assert r.code == 204
        assert r.reason == 'No Content'


async def is_kernel_running(fetch, kernel_id):
    """Issues request to get the set of running kernels
    """
    with mocked_gateway:
        # Get list of running kernels
        r = await fetch(
            'api', 'kernels',
            method='GET'
        )
        assert r.code == 200
        kernels = json.loads(r.body.decode('utf-8'), encoding='utf-8')
        assert len(kernels) == len(running_kernels)
        for model in kernels:
            if model.get('id') == kernel_id:
                return True
        return False


async def create_kernel(fetch, kernel_name):
    """Issues request to retart the given kernel
    """
    with mocked_gateway:
        body = json.dumps({'name': kernel_name})

        # add a KERNEL_ value to the current env and we'll ensure that that value exists in the mocked method
        os.environ['KERNEL_KSPEC_NAME'] = kernel_name

        r = await fetch(
            'api', 'kernels',
            method='POST',
            body=body
        )
        assert r.code == 201
        model = json.loads(r.body.decode('utf-8'), encoding='utf-8')
        kernel_id = model.get('id')
        # ensure its in the running_kernels and name matches.
        running_kernel = running_kernels.get(kernel_id)
        assert kernel_id == running_kernel.get('id')
        assert model.get('name') == kernel_name

        # restore env
        os.environ.pop('KERNEL_KSPEC_NAME')
        return kernel_id


async def interrupt_kernel(fetch, kernel_id):
    """Issues request to interrupt the given kernel
    """
    with mocked_gateway:
        r = await fetch(
            'api', 'kernels', kernel_id, 'interrupt',
            method='POST',
            allow_nonstandard_methods=True
        )
        assert r.code == 204
        assert r.reason == 'No Content'


async def restart_kernel(fetch, kernel_id):
    """Issues request to retart the given kernel
    """
    with mocked_gateway:
        r = await fetch(
            'api', 'kernels', kernel_id, 'restart',
            method='POST',
            allow_nonstandard_methods=True
        )
        assert r.code == 200
        model = json.loads(r.body.decode('utf-8'), encoding='utf-8')
        restarted_kernel_id = model.get('id')
        # ensure its in the running_kernels and name matches.
        running_kernel = running_kernels.get(restarted_kernel_id)
        assert restarted_kernel_id == running_kernel.get('id')
        assert model.get('name') == running_kernel.get('name')


async def delete_kernel(fetch, kernel_id):
    """Deletes kernel corresponding to the given kernel id.
    """
    with mocked_gateway:
        # Delete the session (and kernel)
        r = await fetch(
            'api', 'kernels', kernel_id,
            method='DELETE'
        )
        assert r.code == 204
        assert r.reason == 'No Content'
