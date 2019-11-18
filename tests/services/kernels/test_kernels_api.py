import json
import pytest

import tornado

from jupyter_client.kernelspec import NATIVE_KERNEL_NAME


# Run all tests in this module using asyncio's event loop
pytestmark = pytest.mark.asyncio


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
    assert e.value.code == 404

    # Delete kernel with id.
    r = await fetch(
        'api', 'kernels', 
    )