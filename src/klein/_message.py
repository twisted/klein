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

from zope.interface import Attribute, Interface

from ._headers import IHTTPHeaders
from ._tubes import bytesToFount, fountToBytes

Any, Deferred, IFount, IHTTPHeaders, Optional  # Silence linter


__all__ = ()



# Interfaces

class NoFountError(Exception):
    """
    Request has no fount.
    This implies someone already accessed the body fount.
    """



class IHTTPMessage(Interface):
    """
    HTTP entity.
    """

    headers = Attribute("Entity headers.")  # type: IHTTPHeaders


    def bodyAsFount():
        # type: () -> IFount
        """
        The entity body, as a fount.

        @note: The fount may only be accessed once.
            It provides a mechanism for accessing the body as a stream of data,
            potentially as it is read from the network, without having to cache
            the entire body, which may be large.
            Because there is no caching, it is not possible to "start over" by
            accessing the fount a second time.
            Attempting to do so will raise L{NoFountError}.

        @raise NoFountError: If the fount has previously been accessed.
        """


    def bodyAsBytes():
        # type: () -> Deferred[bytes]
        """
        The entity body, as bytes.

        @note: This necessarily reads the entire entity body into memory,
            which may be a problem if the body is large.

        @note: This method caches the body, which means that unlike
            C{self.bodyAsFount}, calling it repeatedly will return the same
            data.

        @note: This method accesses the fount (via C{self.bodyAsFount}), which
            means the fount will not be available afterwards, and that if
            C{self.bodyAsFount} has previously been called directly, this
            method will raise L{NoFountError}.

        @raise NoFountError: If the fount has previously been accessed.
        """



# Code shared by internal implementations of IHTTPMessage

InternalBody = Union[bytes, IFount]



@attrs(frozen=False)
class MessageState(object):
    """
    Internal mutable state for HTTP message implementations in L{klein}.
    """

    cachedBody = attrib(
        validator=optional(instance_of(bytes)), default=None, init=False
    )  # type: Optional[bytes]

    fountExhausted = attrib(
        validator=instance_of(bool), default=False, init=False
    )  # type: bool



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
        raise NoFountError()
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
