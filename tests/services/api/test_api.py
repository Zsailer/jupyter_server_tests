import pytest

from jupyter_server.utils import url_path_join


@pytest.mark.gen_test
def test_get_spec(http_client, base_url, auth_header):
    url = url_path_join(base_url, 'api', 'spec.yaml')
    response = yield http_client.fetch(
        url,
        method='GET',
        headers=auth_header
    )
    assert response.code == 200
