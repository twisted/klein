from __future__ import absolute_import

from klein import Klein
from klein.resource import KleinHTTPRequest, KleinSite
from klein.test.util import TestCase
from twisted.web.test.requesthelper import DummyChannel

class BytesUnicodeTest(TestCase):

    def setUp(self):
        self.encoding = 'utf-8'
        app = Klein()
        site = KleinSite(app.resource())
        channel = site.buildProtocol('127.0.0.1')
        self.request = channel.requestFactory(DummyChannel(), None)
        self.request.args = {}

    def test_getArg(self):
        str_key = 'test'
        bytes_key = str_key.encode(self.encoding)
        value = b'hello world'

        self.request.args[bytes_key] = [value]
        self.assertEquals(self.request.getArg(str_key), value)
        self.assertEquals(self.request.getArg(bytes_key), value)

    def test_getArg_not_1(self):
        """
        Raise exception if there are more or less values than 1
        """
        str_key = 'test'
        bytes_key = str_key.encode(self.encoding)
        values = []

        self.request.args[bytes_key] = values
        self.assertRaises(ValueError, self.request.getArg, str_key)
        self.assertRaises(ValueError, self.request.getArg, bytes_key)

        values.extend([b'hello', b'world'])
        self.assertRaises(ValueError, self.request.getArg, str_key)
        self.assertRaises(ValueError, self.request.getArg, bytes_key)

    def test_getArgs(self):
        str_key = 'test'
        bytes_key = str_key.encode(self.encoding)
        values = [b'hello world', b'hey earth']
        self.request.args[bytes_key] = values

        self.assertEquals(len(self.request.getArgs(str_key)), len(values))
        self.assertEquals(self.request.getArgs(str_key), values)
        self.assertEquals(self.request.getArgs(bytes_key), values)

    def test_getArgs_no_key(self):
        """
        By default, an empty list is returned if a key doesn't exist
        """
        str_key = 'test'
        bytes_key = str_key.encode(self.encoding)

        self.assertEquals(self.request.getArgs(str_key), [])
        self.assertEquals(self.request.getArgs(bytes_key), [])
