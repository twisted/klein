# -*- test-case-name: klein.test.test_message -*-
# Copyright (c) 2011-2021. See LICENSE for details.

"""
Tests for L{klein._message}.
"""

from abc import ABC, abstractmethod
from typing import cast

from hypothesis import given
from hypothesis.strategies import binary

from twisted.internet.defer import ensureDeferred

from .._imessage import IHTTPMessage
from .._message import FountAlreadyAccessedError, bytesToFount, fountToBytes
from ._trial import TestCase


__all__ = ()


class FrozenHTTPMessageTestsMixIn(ABC):
    """
    Mix-In class for implementations of IHTTPMessage.
    """

    @classmethod
    @abstractmethod
    def messageFromBytes(cls, data: bytes = b"") -> IHTTPMessage:
        """
        Return a new instance of an L{IHTTPMessage} implementation using the
        given bytes as the message body.
        """

    @classmethod
    def messageFromFountFromBytes(cls, data: bytes = b"") -> IHTTPMessage:
        """
        Return a new instance of an L{IHTTPMessage} implementation using a
        fount containing the given bytes as the message body.
        """
        return cls.messageFromBytes(bytesToFount(data))

    def test_interface_message(self) -> None:
        """
        Message instance implements L{IHTTPMessage}.
        """
        message = self.messageFromBytes()
        cast(TestCase, self).assertProvides(IHTTPMessage, message)

    @given(binary())
    def test_bodyAsFountFromBytes(self, data: bytes) -> None:
        """
        C{bodyAsFount} returns a fount with the same bytes given to
        C{__init__}.
        """
        message = self.messageFromBytes(data)
        fount = message.bodyAsFount()
        body = cast(TestCase, self).successResultOf(
            ensureDeferred(fountToBytes(fount))
        )

        cast(TestCase, self).assertEqual(body, data)

    @given(binary())
    def test_bodyAsFountFromBytesTwice(self, data: bytes) -> None:
        """
        C{bodyAsFount} raises L{FountAlreadyAccessedError} if called more than
        once, when created from bytes.
        """
        message = self.messageFromBytes(data)
        message.bodyAsFount()
        cast(TestCase, self).assertRaises(
            FountAlreadyAccessedError, message.bodyAsFount
        )

    @given(binary())
    def test_bodyAsFountFromFount(self, data: bytes) -> None:
        """
        C{bodyAsBytes} returns the bytes from the fount given to C{__init__}.
        """
        message = self.messageFromFountFromBytes(data)
        fount = message.bodyAsFount()
        body = cast(TestCase, self).successResultOf(
            ensureDeferred(fountToBytes(fount))
        )
        cast(TestCase, self).assertEqual(body, data)

    @given(binary())
    def test_bodyAsFountFromFountTwice(self, data: bytes) -> None:
        """
        C{bodyAsFount} raises L{FountAlreadyAccessedError} if called more than
        once, when created from a fount.
        """
        message = self.messageFromFountFromBytes(data)
        message.bodyAsFount()
        cast(TestCase, self).assertRaises(
            FountAlreadyAccessedError, message.bodyAsFount
        )

    @given(binary())
    def test_bodyAsBytesFromBytes(self, data: bytes) -> None:
        """
        C{bodyAsBytes} returns the same bytes given to C{__init__}.
        """
        message = self.messageFromBytes(data)
        body = cast(TestCase, self).successResultOf(
            ensureDeferred(message.bodyAsBytes())
        )
        cast(TestCase, self).assertEqual(body, data)

    @given(binary())
    def test_bodyAsBytesFromBytesCached(self, data: bytes) -> None:
        """
        C{bodyAsBytes} called twice returns the same object both times, when
        created from bytes.
        """
        message = self.messageFromBytes(data)
        body1 = cast(TestCase, self).successResultOf(
            ensureDeferred(message.bodyAsBytes())
        )
        body2 = cast(TestCase, self).successResultOf(
            ensureDeferred(message.bodyAsBytes())
        )
        cast(TestCase, self).assertIdentical(body1, body2)

    @given(binary())
    def test_bodyAsBytesFromFount(self, data: bytes) -> None:
        """
        C{bodyAsBytes} returns the bytes from the fount given to C{__init__}.
        """
        message = self.messageFromFountFromBytes(data)
        body = cast(TestCase, self).successResultOf(
            ensureDeferred(message.bodyAsBytes())
        )
        cast(TestCase, self).assertEqual(body, data)

    @given(binary())
    def test_bodyAsBytesFromFountCached(self, data: bytes) -> None:
        """
        C{bodyAsBytes} called twice returns the same object both times, when
        created from a fount.
        """
        message = self.messageFromFountFromBytes(data)
        body1 = cast(TestCase, self).successResultOf(
            ensureDeferred(message.bodyAsBytes())
        )
        body2 = cast(TestCase, self).successResultOf(
            ensureDeferred(message.bodyAsBytes())
        )
        cast(TestCase, self).assertIdentical(body1, body2)
