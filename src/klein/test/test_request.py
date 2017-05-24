# -*- test-case-name: klein.test.test_request -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{klein._request}.
"""

from string import ascii_uppercase

from hypothesis import given, note
from hypothesis.strategies import text

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
    def test_url(self, url):
        """
        L{HTTPRequest.url} matches the underlying legacy request URL.
        """
        url = url.asURI()  # Normalize as (network-friendly) URI

        host = url.host.encode("ascii")
        path = url.replace(scheme=u"", host=u"", port=None).asText()

        note("path: {!r}".format(path))

        legacyRequest = self.webRequest(
            isSecure=(url.scheme == u"https"),
            host=url.host.encode("ascii"), port=url.port,
            path=path.encode("ascii"),
        )
        request = HTTPRequest(request=legacyRequest)

        # # Work around for https://github.com/mahmoud/hyperlink/issues/5
        def normalize(url):
            return url.replace(path=(s for s in url.path if s))

        self.assertEqual(normalize(request.url), normalize(url))
