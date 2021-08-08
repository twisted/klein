# -*- test-case-name: klein.test.test_headers_compat -*-
# Copyright (c) 2011-2021. See LICENSE for details.

"""
Tests for L{klein._headers}.
"""

from twisted.web.http_headers import Headers

from .._headers import (
    IMutableHTTPHeaders,
    RawHeaders,
    normalizeRawHeadersFrozen,
)
from .._headers_compat import HTTPHeadersWrappingHeaders
from ._trial import TestCase
from .test_headers import MutableHTTPHeadersTestsMixIn


try:
    from twisted.web.http_headers import _sanitizeLinearWhitespace
except ImportError:  # pragma: no cover
    _sanitizeLinearWhitespace = None  # type: ignore[assignment]


def _twistedHeaderNormalize(value: str) -> str:
    """
    Normalize the given header value according to the rules of the installed
    Twisted version.
    """
    if _sanitizeLinearWhitespace is None:  # pragma: no cover
        return value  # type: ignore[unreachable]
    else:
        return _sanitizeLinearWhitespace(value.encode("utf-8")).decode("utf-8")


__all__ = ()


class HTTPHeadersWrappingHeadersTests(MutableHTTPHeadersTestsMixIn, TestCase):
    """
    Tests for L{HTTPHeadersWrappingHeaders}.
    """

    def assertRawHeadersEqual(
        self, rawHeaders1: RawHeaders, rawHeaders2: RawHeaders
    ) -> None:
        super().assertRawHeadersEqual(sorted(rawHeaders1), sorted(rawHeaders2))

    def headerNormalize(self, value: str) -> str:
        return _twistedHeaderNormalize(value)

    def headers(self, rawHeaders: RawHeaders) -> IMutableHTTPHeaders:
        headers = Headers()
        for rawName, rawValue in rawHeaders:
            headers.addRawHeader(rawName, rawValue)

        return HTTPHeadersWrappingHeaders(headers=headers)

    def test_rawHeaders(self) -> None:
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
