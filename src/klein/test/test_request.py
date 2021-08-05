# -*- test-case-name: klein.test.test_request -*-
# Copyright (c) 2011-2021. See LICENSE for details.

"""
Tests for L{klein._request}.
"""

from hyperlink import DecodedURL

from .._headers import FrozenHTTPHeaders
from .._imessage import IHTTPMessage
from .._request import FrozenHTTPRequest, IHTTPRequest
from ._trial import TestCase
from .test_message import FrozenHTTPMessageTestsMixIn


__all__ = ()


class FrozenHTTPRequestTests(FrozenHTTPMessageTestsMixIn, TestCase):
    """
    Tests for L{FrozenHTTPRequest}.
    """

    @staticmethod
    def requestFromBytes(data: bytes = b"") -> FrozenHTTPRequest:
        return FrozenHTTPRequest(
            method="GET",
            uri=DecodedURL.fromText("https://twistedmatrix.com/"),
            headers=FrozenHTTPHeaders(rawHeaders=()),
            body=data,
        )

    @classmethod
    def messageFromBytes(cls, data: bytes = b"") -> IHTTPMessage:
        return cls.requestFromBytes(data)

    def test_interface(self) -> None:
        """
        L{FrozenHTTPRequest} implements L{IHTTPRequest}.
        """
        request = self.requestFromBytes()
        self.assertProvides(IHTTPRequest, request)

    def test_initInvalidBodyType(self) -> None:
        """
        L{FrozenHTTPRequest} raises L{TypeError} when given a body of an
        unknown type.
        """
        e = self.assertRaises(
            TypeError,
            FrozenHTTPRequest,
            method="GET",
            uri=DecodedURL.fromText("https://twistedmatrix.com/"),
            headers=FrozenHTTPHeaders(rawHeaders=()),
            body=object(),
        )
        self.assertEqual(str(e), "body must be bytes or IFount")
