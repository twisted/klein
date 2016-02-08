from __future__ import absolute_import, division

import os
from mock import Mock
from twisted.trial import unittest
from twisted.python.compat import unicode

import setup


class SetupTestCase(unittest.TestCase):
    """
    Tests for helper functions whithin setup.py.
    """
    def test_read(self):
        """
        Reads a file and returns unicode.
        """
        contents = 'foo'
        path = os.path.abspath(self.mktemp())
        with open(path, 'wt') as f:
            f.write(contents)

        rv = setup.read(path)
        self.assertEqual(contents, rv)
        self.assertIsInstance(rv, unicode)

    def test_findVersion(self):
        """
        Finds the version that follows our scheme.
        """
        self.patch(setup, 'read', Mock(return_value='''
from something import something_else

__author__ = "Foo"
__version__ = "4.2.0"
__license__ = 'MIT'
'''))
        self.assertEqual(
            u"4.2.0",
            setup.find_version('paths', 'do', 'not', 'matter')
        )
