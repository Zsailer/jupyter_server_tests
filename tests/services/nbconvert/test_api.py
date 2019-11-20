import json
import pytest

# Run all tests in this module using asyncio's event loop
pytestmark = pytest.mark.asyncio

async def test_list_formats(fetch):
    r = await fetch(
        'api', 'nbconvert',
        method='GET'
    )
    formats = json.loads(r.body)
    assert isinstance(formats, dict)
    assert 'python' in formats
    assert 'html' in formats
    assert formats['python']['output_mimetype'] == 'text/x-python'