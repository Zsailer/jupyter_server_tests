from traitlets.tests.utils import check_help_all_output


def test_help_output():
    check_help_all_output('jupyter_server.extensions')
    check_help_all_output('jupyter_server.extensions', ['enable'])
    check_help_all_output('jupyter_server.extensions', ['disable'])
    check_help_all_output('jupyter_server.extensions', ['install'])
    check_help_all_output('jupyter_server.extensions', ['uninstall'])


outer_file = __file__


class MockExtensionModule(object):
    __file__ = outer_file

    @staticmethod
    def _jupyter_server_extension_paths():
        return [{
            'module': '_mockdestination/index'
        }]

    loaded = False

    def load_jupyter_server_extension(self, app):
        self.loaded = True