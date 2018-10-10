# -*- test-case-name: klein.test.test_request -*-
# Copyright (c) 2017-2018. See LICENSE for details.

"""
Tests for L{klein._request}.
"""

from hyperlink import DecodedURL

from ._trial import TestCase
from .test_message import FrozenHTTPMessageTestsMixIn
from .._headers import FrozenHTTPHeaders
from .._message import IHTTPMessage
from .._request import FrozenHTTPRequest, IHTTPRequest

IHTTPMessage  # Silence linter


__all__ = ()



class FrozenHTTPRequestTests(FrozenHTTPMessageTestsMixIn, TestCase):
    """
    Tests for L{FrozenHTTPRequest}.
    """

    @staticmethod
    def requestFromBytes(data=b""):
        # type: (bytes) -> FrozenHTTPRequest
        return FrozenHTTPRequest(
            method=u"GET",
            uri=DecodedURL.fromText(u"https://twistedmatrix.com/"),
            headers=FrozenHTTPHeaders(rawHeaders=()),
            body=data,
        )


    @classmethod
    def messageFromBytes(cls, data=b""):
        # type: (bytes) -> IHTTPMessage
        return cls.requestFromBytes(data)


    def test_interface(self):
        # type: () -> None
        """
        L{FrozenHTTPRequest} implements L{IHTTPRequest}.
        """
        request = self.requestFromBytes()
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
            uri=DecodedURL.fromText(u"https://twistedmatrix.com/"),
            headers=FrozenHTTPHeaders(rawHeaders=()),
            body=object(),
        )
        self.assertEqual(str(e), "body must be bytes or IFount")
