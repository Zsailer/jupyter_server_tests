import time
import json
import pytest


import tornado
import urllib.parse
from tornado.escape import url_escape

from jupyter_client.kernelspec import NATIVE_KERNEL_NAME

from jupyter_server.utils import url_path_join

# Run all tests in this module using asyncio's event loop
pytestmark = pytest.mark.asyncio


@pytest.fixture
def ws_fetch(auth_header, http_port):
    """fetch fixture that handles auth, base_url, and path"""
    def client_fetch(*parts, headers={}, params={}, **kwargs):
        # Handle URL strings
        path = url_escape(url_path_join(*parts), plus=False)
        urlparts = urllib.parse.urlparse('ws://localhost:{}'.format(http_port))
        urlparts = urlparts._replace(
            path=path,
            query=urllib.parse.urlencode(params),
        )
        url = urlparts.geturl()
        # Add auth keys to header
        headers.update(auth_header)
        # Make request.
        req = tornado.httpclient.HTTPRequest(
            url, 
            headers=auth_header
        )
        return tornado.websocket.websocket_connect(req)
    return client_fetch


def expected_http_error(error, expected_code, expected_message=None):
    """Check that the error matches the expected output error."""
    if expected_code != error.value.code:
        return False
    if expected_message:
        message = json.loads(error.value.response.body)['message']
        if expected_message != message:
            return False
    return True


async def test_no_kernels(fetch):
    r = await fetch(
        'api', 'kernels',
        method='GET'
    )
    kernels = json.loads(r.body)
    assert kernels == []


async def test_default_kernels(fetch):
    r = await fetch(
        'api', 'kernels',
        method='POST',
        allow_nonstandard_methods=True
    )
    kernel = json.loads(r.body)
    assert r.headers['location'] == '/api/kernels/' + kernel['id']
    assert r.code == 201
    assert isinstance(kernel, dict)

    report_uri = '/api/security/csp-report'
    expected_csp = '; '.join([
        "frame-ancestors 'self'",
        'report-uri ' + report_uri,
        "default-src 'none'"
    ])
    assert r.headers['Content-Security-Policy'] == expected_csp


async def test_main_kernel_handler(fetch):
    # Start the first kernel
    r = await fetch(
        'api', 'kernels',
        method='POST',
        body=json.dumps({
            'name': NATIVE_KERNEL_NAME
        })
    )
    kernel1 = json.loads(r.body)
    assert r.headers['location'] == '/api/kernels/' + kernel1['id']
    assert r.code == 201
    assert isinstance(kernel1, dict)

    report_uri = '/api/security/csp-report'
    expected_csp = '; '.join([
        "frame-ancestors 'self'",
        'report-uri ' + report_uri,
        "default-src 'none'"
    ])
    assert r.headers['Content-Security-Policy'] == expected_csp

    # Check that the kernel is found in the kernel list
    r = await fetch(
        'api', 'kernels',
        method='GET'
    )
    kernel_list = json.loads(r.body)
    assert r.code == 200
    assert isinstance(kernel_list, list)
    assert kernel_list[0]['id'] == kernel1['id']
    assert kernel_list[0]['name'] == kernel1['name']

    # Start a second kernel
    r = await fetch(
        'api', 'kernels',
        method='POST',
        body=json.dumps({
            'name': NATIVE_KERNEL_NAME
        })
    )
    kernel2 = json.loads(r.body)
    assert isinstance(kernel2, dict)

    # Get kernel list again
    r = await fetch(
        'api', 'kernels',
        method='GET'
    )
    kernel_list = json.loads(r.body)
    assert r.code == 200
    assert isinstance(kernel_list, list)
    assert len(kernel_list) == 2

    # Interrupt a kernel
    r = await fetch(
        'api', 'kernels', kernel2['id'], 'interrupt',
        method='POST',
        allow_nonstandard_methods=True
    )
    assert r.code == 204

    # Restart a kernel
    r = await fetch(
        'api', 'kernels', kernel2['id'], 'restart',
        method='POST',
        allow_nonstandard_methods=True
    )
    restarted_kernel = json.loads(r.body)
    assert restarted_kernel['id'] == kernel2['id']
    assert restarted_kernel['name'] == kernel2['name']


async def test_kernel_handler(fetch):
    # Create a kernel
    r = await fetch(
        'api', 'kernels',
        method='POST',
        body=json.dumps({
            'name': NATIVE_KERNEL_NAME
        })
    )
    kernel_id = json.loads(r.body)['id']
    r = await fetch(
        'api', 'kernels', kernel_id,
        method='GET'
    )
    kernel = json.loads(r.body)
    assert r.code == 200
    assert isinstance(kernel, dict)
    assert 'id' in kernel
    assert kernel['id'] == kernel_id

    # Requests a bad kernel id.
    bad_id = '111-111-111-111-111'
    with pytest.raises(tornado.httpclient.HTTPClientError) as e:
        r = await fetch(
            'api', 'kernels', bad_id,
            method='GET'
        )
    assert expected_http_error(e, 404)

    # Delete kernel with id.
    r = await fetch(
        'api', 'kernels', kernel_id,
        method='DELETE',
    )
    assert r.code == 204

    # Get list of kernels
    r = await fetch(
        'api', 'kernels',
        method='GET'
    )
    kernel_list = json.loads(r.body)
    assert kernel_list == []

    # Request to delete a non-existent kernel id
    bad_id = '111-111-111-111-111'
    with pytest.raises(tornado.httpclient.HTTPClientError) as e:
        r = await fetch(
            'api', 'kernels', bad_id,
            method='DELETE'
        )
    assert expected_http_error(e, 404, 'Kernel does not exist: ' + bad_id)


async def test_connection(fetch, ws_fetch, http_port, auth_header):
    # Create kernel
    r = await fetch(
        'api', 'kernels',
        method='POST',
        body=json.dumps({
            'name': NATIVE_KERNEL_NAME
        })
    )
    kid = json.loads(r.body)['id']
    
    # Get kernel info
    r = await fetch(
        'api', 'kernels', kid,
        method='GET'
    )
    model = json.loads(r.body)
    assert model['connections'] == 0

    # Open a websocket connection.
    ws = await ws_fetch(
        'api', 'kernels', kid, 'channels'
    )
    
    # Test that it was opened.
    r = await fetch(
        'api', 'kernels', kid,
        method='GET'
    )
    model = json.loads(r.body)
    assert model['connections'] == 1

    # Close websocket
    ws.close()
    # give it some time to close on the other side:
    for i in range(10):
        r = await fetch(
            'api', 'kernels', kid,
            method='GET'
        )
        model = json.loads(r.body)
        if model['connections'] > 0:
            time.sleep(0.1)
        else:
            break
    
    r = await fetch(
        'api', 'kernels', kid,
        method='GET'
    )
    model = json.loads(r.body)
    assert model['connections'] == 0


async def test_config2(serverapp):
    assert serverapp.kernel_manager.allowed_message_types == []

