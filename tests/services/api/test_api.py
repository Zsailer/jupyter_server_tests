import pytest

from jupyter_server.utils import url_path_join


@pytest.mark.gen_test
def test_get_spec(fetch):
    response = yield fetch(
        'api', 'spec.yaml',
        method='GET'
    )
    assert response.code == 200



