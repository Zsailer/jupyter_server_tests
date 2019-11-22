import pytest

from jupyter_server.serverapp import ServerApp
from jupyter_server.extension.application import ExtensionApp
from jupyter_server.extension.handler import ExtensionHandler


# Run all tests in this module using asyncio's event loop
pytestmark = pytest.mark.asyncio


# --------------- Build a mock extension --------------

class MockExtensionHandler(ExtensionHandler):

    def get(self):
        self.finish('mock')


class MockExtension(ExtensionApp):
    extension_name = 'mock'

    def initialize_handlers(self):
        self.handlers.append(('/mock', MockExtensionHandler))

# ------------------ Start tests -------------------

# def test_instance_creation(serverapp):
#     extension = MockExtension()
#     extension.initialize(serverapp)
#     assert isinstance(extension.serverapp, ServerApp)


@pytest.fixture
def mock_extension(serverapp):
    m = MockExtension()
    m.initialize(serverapp)
    return m


async def test_api(fetch, mock_extension):
    r = await fetch(
        'mock',
        method='GET'
    )
    assert r.code == 200
    assert r.body.decode() == 'mock'