# -*- test-case-name: klein.test.test_headers_compat -*-
# Copyright (c) 2017-2018. See LICENSE for details.

"""
Tests for L{klein._headers}.
"""

from twisted.web.http_headers import Headers

from ._trial import TestCase
from .test_headers import MutableHTTPHeadersTestsMixIn
from .._headers import (
    IMutableHTTPHeaders, RawHeaders, normalizeRawHeadersFrozen
)
from .._headers_compat import HTTPHeadersWrappingHeaders

# Silence linter
IMutableHTTPHeaders, RawHeaders


__all__ = ()



class HTTPHeadersWrappingHeadersTests(MutableHTTPHeadersTestsMixIn, TestCase):
    """
    Tests for L{HTTPHeadersWrappingHeaders}.
    """

    def assertRawHeadersEqual(self, rawHeaders1, rawHeaders2):
        # type: (RawHeaders, RawHeaders) -> None
        super(HTTPHeadersWrappingHeadersTests, self).assertRawHeadersEqual(
            sorted(rawHeaders1), sorted(rawHeaders2)
        )


    def headers(self, rawHeaders):
        # type: (RawHeaders) -> IMutableHTTPHeaders
        headers = Headers()
        for rawName, rawValue in rawHeaders:
            headers.addRawHeader(rawName, rawValue)

        return HTTPHeadersWrappingHeaders(headers=headers)


    def test_rawHeaders(self):
        # type: () -> None
        """
        L{MutableHTTPHeaders.rawHeaders} equals raw headers matching the
        L{Headers} given at init time.
        """
        rawHeaders = ((b"b", b"2a"), (b"a", b"1"), (b"B", b"2b"))
        webHeaders = Headers()
        for name, value in rawHeaders:
            webHeaders.addRawHeader(name, value)
        headers = HTTPHeadersWrappingHeaders(headers=webHeaders)

        # Note that Headers does not give you back header names in network
        # order, but it should give us back values in network order.
        # So we need to normalize our way around.

        normalizedRawHeaders = normalizeRawHeadersFrozen(rawHeaders)

        self.assertEqual(
            sorted(headers.rawHeaders), sorted(normalizedRawHeaders)
        )
