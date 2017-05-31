# -*- test-case-name: klein.test.test_request -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{klein._request}.
"""

from string import ascii_uppercase
from typing import Dict, List, Optional, Text, Tuple

from hyperlink import URL

from hypothesis import given, note
from hypothesis.strategies import binary, text

from twisted.web.http_headers import Headers
from twisted.web.iweb import IRequest

from ._strategies import http_urls
from ._trial import TestCase
from .test_resource import requestMock
from .._headers import FrozenHTTPHeaders, IHTTPHeaders
from .._request import (
    FrozenHTTPRequest, HTTPRequestFromIRequest, IHTTPRequest, NoContentError,
    bytesToFount, fountToBytes,
)

Dict, Headers, IRequest, List, Optional, Text, Tuple  # Silence linter


__all__ = ()



class FrozenHTTPRequestTests(TestCase):
    """
    Tests for L{FrozenHTTPRequest}.
    """

    def test_interface(self):
        # type: () -> None
        """
        L{FrozenHTTPRequest} implements L{IHTTPRequest}.
        """
        request = FrozenHTTPRequest(
            method=u"GET",
            uri=URL.fromText(u"https://twistedmatrix.com/"),
            headers=FrozenHTTPHeaders(rawHeaders=()),
            body=b"",
        )
        self.assertProvides(IHTTPRequest, request)


    def test_initInvalidBodyType(self):
        # type: () -> None
        """
        L{FrozenHTTPRequest} raises L{TypeError} when given a body of an
        unknown type.
        """
        e = self.assertRaises(
            TypeError,
            FrozenHTTPRequest,
            method=u"GET",
            uri=URL.fromText(u"https://twistedmatrix.com/"),
            headers=FrozenHTTPHeaders(rawHeaders=()),
            body=object(),
        )
        self.assertEqual(str(e), "body must be bytes or IFount")


    @given(binary())
    def test_bodyAsFountFromBytes(self, data):
        # type: (bytes) -> None
        """
        L{FrozenHTTPRequest.bodyAsFount} returns a fount with the same bytes
        given to C{__init__}.
        """
        request = FrozenHTTPRequest(
            method=u"GET",
            uri=URL.fromText(u"https://twistedmatrix.com/"),
            headers=FrozenHTTPHeaders(rawHeaders=()),
            body=data,
        )
        fount = request.bodyAsFount()
        body = self.successResultOf(fountToBytes(fount))

        self.assertEqual(body, data)


    @given(binary())
    def test_bodyAsFountFromFount(self, data):
        # type: (bytes) -> None
        """
        L{FrozenHTTPRequest.bodyAsBytes} returns the bytes from the fount given
        to C{__init__}.
        """
        request = FrozenHTTPRequest(
            method=u"GET",
            uri=URL.fromText(u"https://twistedmatrix.com/"),
            headers=FrozenHTTPHeaders(rawHeaders=()),
            body=bytesToFount(data),
        )
        fount = request.bodyAsFount()
        body = self.successResultOf(fountToBytes(fount))

        self.assertEqual(body, data)


    @given(binary())
    def test_bodyAsBytesFromBytes(self, data):
        # type: (bytes) -> None
        """
        L{FrozenHTTPRequest.bodyAsBytes} returns the same bytes given to
        C{__init__}.
        """
        request = FrozenHTTPRequest(
            method=u"GET",
            uri=URL.fromText(u"https://twistedmatrix.com/"),
            headers=FrozenHTTPHeaders(rawHeaders=()),
            body=data,
        )
        body = self.successResultOf(request.bodyAsBytes())

        self.assertEqual(body, data)


    @given(binary())
    def test_bodyAsBytesFromFount(self, data):
        # type: (bytes) -> None
        """
        L{FrozenHTTPRequest.bodyAsBytes} returns the bytes from the fount given
        to C{__init__}.
        """
        request = FrozenHTTPRequest(
            method=u"GET",
            uri=URL.fromText(u"https://twistedmatrix.com/"),
            headers=FrozenHTTPHeaders(rawHeaders=()),
            body=bytesToFount(data),
        )
        body = self.successResultOf(request.bodyAsBytes())
        self.assertEqual(body, data)



class HTTPRequestFromIRequestTests(TestCase):
    """
    Tests for L{HTTPRequestFromIRequest}.
    """

    def legacyRequest(
        self,
        path=b"/",          # type: bytes
        method=b"GET",      # type: bytes
        host=b"localhost",  # type: bytes
        port=8080,          # type: int
        isSecure=False,     # type: bool
        body=None,          # type: Optional[bytes]
        headers=None,       # type: Optional[Headers]
    ):
        # type: (...) -> IRequest
        return requestMock(
            path=path, method=method, host=host, port=port,
            isSecure=isSecure, body=body, headers=headers,
        )


    def test_interface(self):
        # type: () -> None
        """
        L{HTTPRequestFromIRequest} implements L{IHTTPRequest}.
        """
        request = HTTPRequestFromIRequest(request=self.legacyRequest())
        self.assertProvides(IHTTPRequest, request)


    @given(text(alphabet=ascii_uppercase, min_size=1))
    def test_method(self, methodText):
        # type: (Text) -> None
        """
        L{HTTPRequestFromIRequest.method} matches the underlying legacy request
        method.
        """
        legacyRequest = self.legacyRequest(method=methodText.encode("ascii"))
        request = HTTPRequestFromIRequest(request=legacyRequest)
        self.assertEqual(request.method, methodText)


    @given(http_urls())
    def test_uri(self, url):
        # type: (URL) -> None
        """
        L{HTTPRequestFromIRequest.uri} matches the underlying legacy request
        URI.
        """
        uri = url.asURI()  # Normalize as (network-friendly) URI
        path = (
            uri.replace(scheme=u"", host=u"", port=None)
            .asText()
            .encode("ascii")
        )
        legacyRequest = self.legacyRequest(
            isSecure=(uri.scheme == u"https"),
            host=uri.host.encode("ascii"), port=uri.port, path=path,
        )
        request = HTTPRequestFromIRequest(request=legacyRequest)

        # Work around for https://github.com/mahmoud/hyperlink/issues/5
        def normalize(uri):
            # type: (URL) -> URL
            return uri.replace(path=(s for s in uri.path if s))

        note("_request.uri: {!r}".format(path))
        note("request.uri: {!r}".format(request.uri))

        self.assertEqual(normalize(request.uri), normalize(uri))


    def test_headers(self):
        # type: () -> None
        """
        L{HTTPRequestFromIRequest.headers} returns an
        L{HTTPRequestFromIRequest} containing the underlying legacy request
        headers.
        """
        legacyRequest = self.legacyRequest()
        request = HTTPRequestFromIRequest(request=legacyRequest)
        self.assertProvides(IHTTPHeaders, request.headers)


    def test_bodyAsFountTwice(self):
        # type: () -> None
        """
        L{HTTPRequestFromIRequest.bodyAsFount} raises L{NoContentError} if
        called more than once.
        """
        legacyRequest = self.legacyRequest()
        request = HTTPRequestFromIRequest(request=legacyRequest)
        request.bodyAsFount()
        self.assertRaises(NoContentError, request.bodyAsFount)


    @given(binary())
    def test_bodyAsBytes(self, data):
        # type: (bytes) -> None
        """
        L{HTTPRequestFromIRequest.bodyAsBytes} matches the underlying legacy
        request body.
        """
        legacyRequest = self.legacyRequest(body=data)
        request = HTTPRequestFromIRequest(request=legacyRequest)
        body = self.successResultOf(request.bodyAsBytes())

        self.assertEqual(body, data)


    def test_bodyAsBytesCached(self):
        # type: () -> None
        """
        L{HTTPRequestFromIRequest.bodyAsBytes} matches the underlying legacy
        request body.
        """
        data = b"some data"
        legacyRequest = self.legacyRequest(body=data)
        request = HTTPRequestFromIRequest(request=legacyRequest)
        body1 = self.successResultOf(request.bodyAsBytes())
        body2 = self.successResultOf(request.bodyAsBytes())

        self.assertIdentical(body1, body2)
