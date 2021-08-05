# -*- test-case-name: klein.test.test_response -*-
# Copyright (c) 2011-2021. See LICENSE for details.

"""
Tests for L{klein._response}.
"""

from .._headers import FrozenHTTPHeaders
from .._imessage import IHTTPMessage
from .._response import FrozenHTTPResponse, IHTTPResponse
from ._trial import TestCase
from .test_message import FrozenHTTPMessageTestsMixIn


__all__ = ()


class FrozenHTTPResponseTests(FrozenHTTPMessageTestsMixIn, TestCase):
    """
    Tests for L{FrozenHTTPResponse}.
    """

    @staticmethod
    def responseFromBytes(data: bytes = b"") -> FrozenHTTPResponse:
        return FrozenHTTPResponse(
            status=200,
            headers=FrozenHTTPHeaders(rawHeaders=()),
            body=data,
        )

    @classmethod
    def messageFromBytes(cls, data: bytes = b"") -> IHTTPMessage:
        return cls.responseFromBytes(data)

    def test_interface(self) -> None:
        """
        L{FrozenHTTPResponse} implements L{IHTTPResponse}.
        """
        response = self.responseFromBytes()
        self.assertProvides(IHTTPResponse, response)

    def test_initInvalidBodyType(self) -> None:
        """
        L{FrozenHTTPResponse} raises L{TypeError} when given a body of an
        unknown type.
        """
        e = self.assertRaises(
            TypeError,
            FrozenHTTPResponse,
            status=200,
            headers=FrozenHTTPHeaders(rawHeaders=()),
            body=object(),
        )
        self.assertEqual(str(e), "body must be bytes or IFount")
