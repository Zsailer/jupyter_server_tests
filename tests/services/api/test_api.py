import pytest

from jupyter_server.utils import url_path_join

# Run all tests in this module using asyncio's event loop
pytestmark = pytest.mark.asyncio


async def test_get_spec(fetch):
    response = await fetch(
        'api', 'spec.yaml',
        method='GET'
    )
    assert response.code == 200



