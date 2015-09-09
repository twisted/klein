import os
from mock import Mock
from twisted.trial import unittest

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
        with open(path, 'w') as f:
            f.write(contents)

        rv = setup.read(path)
        self.assertEqual(contents, rv)
        self.assertIsInstance(rv, unicode)
