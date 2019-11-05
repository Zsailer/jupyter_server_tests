
import pytest

from traitlets.tests.utils import check_help_all_output
from jupyter_server.utils import url_escape, url_unescape, is_hidden, is_file_hidden, secure_write
from ipython_genutils.py3compat import cast_unicode
from ipython_genutils.tempdir import TemporaryDirectory
from ipython_genutils.testing.decorators import skip_if_not_win32, skip_win32


def test_help_output():
    check_help_all_output('jupyter_server')



@pytest.mark.parametrize(
    'unescaped,escaped',
    [
        (
            '/this is a test/for spaces/', 
            '/this%20is%20a%20test/for%20spaces/'
        ),
        (
            'notebook with space.ipynb',
            'notebook%20with%20space.ipynb'
        ),
        (
            '/path with a/notebook and space.ipynb',
            '/path%20with%20a/notebook%20and%20space.ipynb'
        ),
        (
            '/ !@$#%^&* / test %^ notebook @#$ name.ipynb',
            '/%20%21%40%24%23%25%5E%26%2A%20/%20test%20%25%5E%20notebook%20%40%23%24%20name.ipynb'
        )
    ]
)
def test_url_escape(unescaped, escaped):
    path = url_escape(unescaped)
    assert path == escaped
    path = url_unescape(escaped)
    assert path == unescaped