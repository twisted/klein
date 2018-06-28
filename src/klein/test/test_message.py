# -*- test-case-name: klein.test.test_message -*-
# Copyright (c) 2017-2018. See LICENSE for details.

"""
Tests for L{klein._message}.
"""

from typing import cast

from hypothesis import given
from hypothesis.strategies import binary

from ._trial import TestCase
from .._message import (
    FountAlreadyAccessedError, IHTTPMessage, bytesToFount, fountToBytes
)


__all__ = ()



class FrozenHTTPMessageTestsMixIn(object):
    """
    Mix-In class for implementations of IHTTPMessage.
    """

    @classmethod
    def messageFromBytes(cls, data=b""):
        # type: (bytes) -> IHTTPMessage
        """
        Return a new instance of an L{IHTTPMessage} implementation using the
        given bytes as the message body.
        """
        raise NotImplementedError(
            "{} must implement getValues()".format(cls)
        )


    @classmethod
    def messageFromFountFromBytes(cls, data=b""):
        # type: (bytes) -> IHTTPMessage
        """
        Return a new instance of an L{IHTTPMessage} implementation using a
        fount containing the given bytes as the message body.
        """
        return cls.messageFromBytes(bytesToFount(data))


    def test_interface_message(self):
        # type: () -> None
        """
        Message instance implements L{IHTTPMessage}.
        """
        message = self.messageFromBytes()
        cast(TestCase, self).assertProvides(IHTTPMessage, message)


    @given(binary())
    def test_bodyAsFountFromBytes(self, data):
        # type: (bytes) -> None
        """
        C{bodyAsFount} returns a fount with the same bytes given to
        C{__init__}.
        """
        message = self.messageFromBytes(data)
        fount = message.bodyAsFount()
        body = cast(TestCase, self).successResultOf(fountToBytes(fount))

        cast(TestCase, self).assertEqual(body, data)


    @given(binary())
    def test_bodyAsFountFromBytesTwice(self, data):
        # type: (bytes) -> None
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
    def test_bodyAsFountFromFount(self, data):
        # type: (bytes) -> None
        """
        C{bodyAsBytes} returns the bytes from the fount given to C{__init__}.
        """
        message = self.messageFromFountFromBytes(data)
        fount = message.bodyAsFount()
        body = cast(TestCase, self).successResultOf(fountToBytes(fount))

        cast(TestCase, self).assertEqual(body, data)


    @given(binary())
    def test_bodyAsFountFromFountTwice(self, data):
        # type: (bytes) -> None
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
    def test_bodyAsBytesFromBytes(self, data):
        # type: (bytes) -> None
        """
        C{bodyAsBytes} returns the same bytes given to C{__init__}.
        """
        message = self.messageFromBytes(data)
        body = cast(TestCase, self).successResultOf(message.bodyAsBytes())

        cast(TestCase, self).assertEqual(body, data)


    @given(binary())
    def test_bodyAsBytesFromBytesCached(self, data):
        # type: (bytes) -> None
        """
        C{bodyAsBytes} called twice returns the same object both times, when
        created from bytes.
        """
        message = self.messageFromBytes(data)
        body1 = cast(TestCase, self).successResultOf(message.bodyAsBytes())
        body2 = cast(TestCase, self).successResultOf(message.bodyAsBytes())

        cast(TestCase, self).assertIdentical(body1, body2)


    @given(binary())
    def test_bodyAsBytesFromFount(self, data):
        # type: (bytes) -> None
        """
        C{bodyAsBytes} returns the bytes from the fount given to C{__init__}.
        """
        message = self.messageFromFountFromBytes(data)
        body = cast(TestCase, self).successResultOf(message.bodyAsBytes())
        cast(TestCase, self).assertEqual(body, data)


    @given(binary())
    def test_bodyAsBytesFromFountCached(self, data):
        # type: (bytes) -> None
        """
        C{bodyAsBytes} called twice returns the same object both times, when
        created from a fount.
        """
        message = self.messageFromFountFromBytes(data)
        body1 = cast(TestCase, self).successResultOf(message.bodyAsBytes())
        body2 = cast(TestCase, self).successResultOf(message.bodyAsBytes())

        cast(TestCase, self).assertIdentical(body1, body2)
