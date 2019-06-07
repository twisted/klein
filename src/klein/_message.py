# -*- test-case-name: klein.test.test_message -*-
# Copyright (c) 2017-2018. See LICENSE for details.

"""
HTTP message API.
"""

from typing import Any, Optional, Union

from attr import attrib, attrs
from attr.validators import instance_of, optional

from tubes.itube import IFount

from twisted.internet.defer import Deferred, succeed

from ._imessage import FountAlreadyAccessedError
from ._interfaces import IHTTPMessage
from ._tubes import bytesToFount, fountToBytes

Any, Deferred, IHTTPMessage, Optional  # Silence linter


__all__ = ()


InternalBody = Union[bytes, IFount]



@attrs(frozen=False)
class MessageState(object):
    """
    Internal mutable state for HTTP message implementations in L{klein}.
    """

    cachedBody = attrib(
        type=Optional[bytes],
        validator=optional(instance_of(bytes)), default=None, init=False
    )

    fountExhausted = attrib(
        type=bool,
        validator=instance_of(bool), default=False, init=False
    )


def validateBody(instance, attribute, body):
    # type: (Any, Any, InternalBody) -> None
    """
    Validator for L{InternalBody}.
    """

    if (
        not isinstance(body, bytes) and
        not IFount.providedBy(body)
    ):
        raise TypeError("body must be bytes or IFount")


def bodyAsFount(body, state):
    # type: (InternalBody, MessageState) -> IFount
    """
    Return a fount for a given L{InternalBody}.
    """

    if state.fountExhausted:
        raise FountAlreadyAccessedError()
    state.fountExhausted = True

    if isinstance(body, bytes):
        return bytesToFount(body)

    # assuming: IFount.providedBy(body)

    return body


def bodyAsBytes(body, state):
    # type: (InternalBody, MessageState) -> Deferred[bytes]
    """
    Return bytes for a given L{InternalBody}.
    """

    if isinstance(body, bytes):
        return succeed(body)

    # assuming: IFount.providedBy(body)

    if state.cachedBody is not None:
        return succeed(state.cachedBody)

    def cache(bodyBytes):
        # type: (bytes) -> bytes
        state.cachedBody = bodyBytes
        return bodyBytes

    d = fountToBytes(body)
    d.addCallback(cache)
    return d
