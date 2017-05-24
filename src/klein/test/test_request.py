# -*- test-case-name: klein.test.test_request -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{klein._request}.
"""

from string import ascii_uppercase

from hypothesis import given, note
from hypothesis.strategies import binary, text

from twisted.trial.unittest import SynchronousTestCase as TestCase

from ._strategies import http_urls
from .test_resource import requestMock
from .._request import HTTPRequest, NoContentError


__all__ = ()



class HTTPRequestTests(TestCase):
    """
    Tests for L{HTTPRequest}.
    """

    def webRequest(
        self, path=b"/", method=b"GET", host=b"localhost", port=8080,
        isSecure=False, body=None, headers=None,
    ):
        return requestMock(
            path=path, method=method, host=host, port=port,
            isSecure=isSecure, body=body, headers=headers,
        )


    @given(text(alphabet=ascii_uppercase, min_size=1))
    def test_method(self, methodText):
        """
        L{HTTPRequest.method} matches the underlying legacy request method.
        """
        legacyRequest = self.webRequest(method=methodText.encode("ascii"))
        request = HTTPRequest(request=legacyRequest)
        self.assertEqual(request.method, methodText)


    @given(http_urls())
    def test_uri(self, url):
        """
        L{HTTPRequest.uri} matches the underlying legacy request URI.
        """
        uri = url.asURI()  # Normalize as (network-friendly) URI
        path = (
            uri.replace(scheme=u"", host=u"", port=None)
            .asText()
            .encode("ascii")
        )
        legacyRequest = self.webRequest(
            isSecure=(uri.scheme == u"https"),
            host=uri.host.encode("ascii"), port=uri.port, path=path,
        )
        request = HTTPRequest(request=legacyRequest)

        # Work around for https://github.com/mahmoud/hyperlink/issues/5
        def normalize(uri):
            return uri.replace(path=(s for s in uri.path if s))

        note("_request.uri: {!r}".format(path))
        note("request.uri: {!r}".format(request.uri))

        self.assertEqual(normalize(request.uri), normalize(uri))


    @given(binary())
    def test_bodyAsBytes(self, data):
        """
        L{HTTPRequest.bodyAsBytes} matches the underlying legacy request body.
        """
        legacyRequest = self.webRequest(body=data)
        request = HTTPRequest(request=legacyRequest)
        body = self.successResultOf(request.bodyAsBytes())

        self.assertEqual(body, data)
