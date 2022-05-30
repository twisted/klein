# -*- test-case-name: klein.test.test_message -*-
# Copyright (c) 2011-2021. See LICENSE for details.

"""
HTTP message API.
"""

from typing import Any, Optional, Union

from attr import attrib, attrs
from attr.validators import instance_of, optional
from tubes.itube import IFount

from ._imessage import FountAlreadyAccessedError
from ._tubes import bytesToFount, fountToBytes


__all__ = ()


InternalBody = Union[bytes, IFount]


@attrs(frozen=False)
class MessageState:
    """
    Internal mutable state for HTTP message implementations in L{klein}.
    """

    cachedBody: Optional[bytes] = attrib(
        validator=optional(instance_of(bytes)), default=None, init=False
    )

    fountExhausted: bool = attrib(
        validator=instance_of(bool), default=False, init=False
    )


def validateBody(instance: Any, attribute: Any, body: InternalBody) -> None:
    """
    Validator for L{InternalBody}.
    """

    if not isinstance(body, bytes) and not IFount.providedBy(body):
        raise TypeError("body must be bytes or IFount")


def bodyAsFount(body: InternalBody, state: MessageState) -> IFount:
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


async def bodyAsBytes(body: InternalBody, state: MessageState) -> bytes:
    """
    Return bytes for a given L{InternalBody}.
    """

    if isinstance(body, bytes):
        return body

    # assuming: IFount.providedBy(body)

    if state.cachedBody is not None:
        return state.cachedBody

    state.cachedBody = await fountToBytes(body)

    return state.cachedBody
