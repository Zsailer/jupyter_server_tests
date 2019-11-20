import json
import pytest

# Run all tests in this module using asyncio's event loop
pytestmark = pytest.mark.asyncio


def get_session_model(
    path, 
    type='notebook', 
    kernel_name='python', 
    kernel_id=None
    ):
    return {
        'path': path,
        'type': type,
        'kernel': {
            'name': kernel_name,
            'id': kernel_id
        }
    }


async def test_create(fetch):
    # Make sure no sessions exist.
    r = await fetch(
        'api', 'sessions',
        method='GET'
    )
    sessions = json.loads(r.body)
    assert len(sessions) == 0

    # Create a session.
    model = get_session_model('foo/nb1.ipynb')
    r = await fetch(
        'api', 'sessions',
        method='POST',
        body=json.dumps(model)
    )
    assert r.code == 201
    new_session = json.loads(r.body)
    assert 'id' in new_session
    assert new_session['path'] == 'foo/nb1.ipynb'
    assert new_session['type'] == 'notebook'
    assert r.headers['Location'] == '/api/sessions/' + new_session['id']

    # Check that the new session appears in list.
    r = await fetch(
        'api', 'sessions',
        method='GET'
    )
    sessions = json.loads(r.body)
    assert sessions == [new_session]

    # Retrieve that session.
    sid = new_session['id']
    r = await fetch(
        'api', 'sessions', sid,
        method='GET'
    )
    got = json.loads(r.body)
    assert got == new_session


