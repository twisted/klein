# -*- test-case-name: klein.test.test_request -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
HTTP headers.
"""

from attr import Factory, attrib, attrs
from attr.validators import instance_of
from typing import (
    Any, AnyStr, Iterable, List, MutableSequence, Sequence, Text,
    Tuple, Union, cast,
)

from twisted.web.http_headers import Headers

from zope.interface import Attribute, Interface, implementer

Any, AnyStr, Iterable, List  # Silence linter


__all__ = ()


# Interfaces

String = Union[bytes, Text]

RawHeader = Tuple[bytes, bytes]
RawHeaders = Sequence[RawHeader]
MutableRawHeaders = MutableSequence[RawHeader]


class IHTTPHeaders(Interface):
    """
    HTTP entity headers.

    HTTP headers names and values are sort-of-but-not-quite-specifically
    expected to be text.

    Because the specifications are somewhat vague, and implementations vary in
    fidelity, both header names and values must be made available as the
    original bytes received from the network.
    This interface also makes them available as an ordered sequence of name and
    value pairs so that they can be iterated in the same order as they were
    received on the network.

    The C{rawHeaders} attribute provides this as a sequence of C{(name, value)}
    L{tuple}s.

    A dictionary-like interface that maps text names to an ordered sequence of
    text values.
    This assumes that header name bytes are encoded as ASCII, and header value
    bytes are encoded as ISO-8859-1.
    """

    rawHeaders = Attribute(
        """
        Raw header data as a tuple in the from: C{((name, value), ...)}.
        C{name} and C{value} are bytes.
        Headers are provided in the order that they were received.
        Headers with multiple values are provided as separate name and value
        pairs.
        """
    )  # type: RawHeaders


    def getValues(name):
        # type: (AnyStr) -> Iterable[AnyStr]
        """
        Get the values associated with the given header name.

        If the given name is L{bytes}, the value will be returned as the
        raw header L{bytes}.

        If the given name is L{Text}, the name will be encoded as ASCII and the
        value will be returned as text, by decoding the raw header value bytes
        with ISO-8859-1.

        @param name: The name of the header to look for.

        @return: The values of the header with the given name.
        """



class IMutableHTTPHeaders(IHTTPHeaders):
    """
    Mutable HTTP entity headers.
    """

    def remove(name):
        # type: (AnyStr) -> None
        """
        Remove all header name/value pairs for the given name,

        If the given name is L{Text}, it will be encoded as ASCII before
        comparing to the (L{bytes}) header names.

        @param name: The name of the header to remove.
        """


    def addValue(name, value):
        # type: (AnyStr, AnyStr) -> None
        """
        Add the given header name/value pair.

        If the given name is L{bytes}, the value must also be L{bytes}.

        If the given name is L{Text}, it will be encoded as ASCII, and the
        value, which must also be L{Text}, will be encoded as ISO-8859-1.
        """



# Encoding/decoding header data

HEADER_NAME_ENCODING  = "iso-8859-1"
HEADER_VALUE_ENCODING = "iso-8859-1"


def headerNameAsBytes(name):
    # type: (String) -> bytes
    """
    Convert a header name to bytes if necessary.
    """
    if type(name) is bytes:
        return cast(bytes, name)
    else:
        return cast(Text, name).encode(HEADER_NAME_ENCODING)


def headerNameAsText(name):
    # type: (String) -> Text
    """
    Convert a header name to text if necessary.
    """
    if type(name) is Text:
        return cast(Text, name)
    else:
        return cast(bytes, name).decode(HEADER_NAME_ENCODING)


def headerValueAsBytes(value):
    # type: (String) -> bytes
    """
    Convert a header value to bytes if necessary.
    """
    if type(value) is bytes:
        return cast(bytes, value)
    else:
        return cast(Text, value).encode(HEADER_VALUE_ENCODING)


def headerValueAsText(value):
    # type: (String) -> Text
    """
    Convert a header value to text if necessary.
    """
    if type(value) is Text:
        return cast(Text, value)
    else:
        return cast(bytes, value).decode(HEADER_VALUE_ENCODING)


# Internal data representation

def validateHeadersTartare(instance, attribute, headerPairs):
    # type: (Any, Any, Iterable[Iterable[bytes]]) -> None
    for pair in headerPairs:
        if not type(pair) is tuple:
            raise TypeError("header pair must be a tuple")

        try:
            name, value = pair
        except ValueError:
            raise ValueError("header pair must be a 2-tuple")

        if type(name) is not bytes:
            raise TypeError("header name must be bytes")
        if type(value) is not bytes:
            raise TypeError("header value must be bytes")


def getFromHeadersTartare(headersTartare, name):
    # type: (RawHeaders, AnyStr) -> Iterable[AnyStr]
    """
    Get a value from raw headers.
    """
    if type(name) is bytes:
        return (v for n, v in headersTartare if name == n)

    if type(name) is Text:
        rawName = headerNameAsBytes(name)
        return(
            headerValueAsText(v)
            for n, v in headersTartare if rawName == n
        )

    raise TypeError("name must be text or bytes")



# Simple implementation

@implementer(IHTTPHeaders)
@attrs(frozen=True)
class FrozenHTTPHeaders(object):
    """
    Immutable HTTP entity headers.
    """

    rawHeaders = attrib(
        convert=tuple, validator=validateHeadersTartare
    )  # type: RawHeaders


    def getValues(self, name):
        # type: (AnyStr) -> Iterable[AnyStr]
        return getFromHeadersTartare(self.rawHeaders, name)



@implementer(IMutableHTTPHeaders)
@attrs(frozen=True)
class MutableHTTPHeaders(object):
    """
    Mutable HTTP entity headers.
    """

    _rawHeaders = attrib(
        convert=list, validator=validateHeadersTartare
    )  # type: MutableRawHeaders


    @property
    def rawHeaders(self):
        # type: () -> RawHeaders
        return tuple(self._rawHeaders)


    def getValues(self, name):
        # type: (AnyStr) -> Iterable[AnyStr]
        return getFromHeadersTartare(self._rawHeaders, name)


    def remove(self, name):
        # type: (String) -> None
        if type(name) is bytes:
            rawName = name
        elif type(name) is Text:
            rawName = headerNameAsBytes(name)
        else:
            raise TypeError("name must be text or bytes")

        self._rawHeaders[:] = [p for p in self._rawHeaders if p[0] != rawName]


    def addValue(self, name, value):
        # type: (AnyStr, AnyStr) -> None
        if type(name) is bytes:
            if type(value) is not bytes:
                raise TypeError("value must be bytes to match name")

            rawName  = name   # type: bytes
            rawValue = value  # type: bytes

        elif type(name) is Text:
            if type(value) is not Text:
                raise TypeError("value must be text to match name")

            rawName  = headerNameAsBytes(name)
            rawValue = headerValueAsBytes(value)

        else:
            raise TypeError("name must be text or bytes")

        self._rawHeaders.append((rawName, rawValue))



# Support for L{Headers}

@implementer(IHTTPHeaders)
@attrs(frozen=True)
class HTTPHeadersFromHeaders(object):
    """
    HTTP entity headers.

    This is an L{IHTTPHeaders} implementation that wraps a L{Headers}
    object.

    This is used by Klein to expose objects from L{twisted.web} to clients
    while presenting the Klein interface.
    """

    @attrs(frozen=False)
    class _State(object):
        """
        Internal mutable state for L{HTTPRequestFromIRequest}.
        """

    _headers = attrib(validator=instance_of(Headers))     # type: Headers
    _state = attrib(default=Factory(_State), init=False)  # type: _State


    @property
    def rawHeaders(self):
        # type: () -> RawHeaders
        raise NotImplementedError()
