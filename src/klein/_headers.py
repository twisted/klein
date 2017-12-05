# -*- test-case-name: txrequest.test.test_request -*-
# Copyright (c) 2017-2018. See LICENSE for details.

"""
HTTP headers API.
"""

from typing import (
    AnyStr, Iterable, List, MutableSequence, Sequence, Text, Tuple, Union
)

from attr import attrib, attrs

from zope.interface import Attribute, Interface, implementer

AnyStr, Iterable, List  # Silence linter


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

    As such, the C{rawHeaders} attribute provides the header data as a sequence
    of C{(name, value)} L{tuple}s.

    A dictionary-like interface that maps text names to an ordered sequence of
    text values.
    This interface assumes that both header name bytes and header value bytes
    are encoded as ISO-8859-1.

    Note that header name bytes should be strictly encoded as ASCII; this
    interface uses ISO-8859-1 to provide interoperability with (naughty) HTTP
    implementations that send non-ASCII data.
    Because ISO-8859-1 is a superset of ASCII, this will still work for
    well-behaved implementations.
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

        If the given name is L{bytes}, the value will be returned as the raw
        header L{bytes}.

        If the given name is L{Text}, the name will be encoded as ISO-8859-1
        and the value will be returned as text, by decoding the raw header
        value bytes with ISO-8859-1.

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
        Remove all header name/value pairs for the given header name.

        If the given name is L{Text}, it will be encoded as ISO-8859-1 before
        comparing to the (L{bytes}) header names.

        @param name: The name of the header to remove.
        """


    def addValue(name, value):
        # type: (AnyStr, AnyStr) -> None
        """
        Add the given header name/value pair.

        If the given name is L{bytes}, the value must also be L{bytes}.

        If the given name is L{Text}, it will be encoded as ISO-8859-1, and the
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
    if isinstance(name, bytes):
        return name
    else:
        return name.encode(HEADER_NAME_ENCODING)


def headerNameAsText(name):
    # type: (String) -> Text
    """
    Convert a header name to text if necessary.
    """
    if isinstance(name, Text):
        return name
    else:
        return name.decode(HEADER_NAME_ENCODING)


def headerValueAsBytes(value):
    # type: (String) -> bytes
    """
    Convert a header value to bytes if necessary.
    """
    if isinstance(value, bytes):
        return value
    else:
        return value.encode(HEADER_VALUE_ENCODING)


def headerValueAsText(value):
    # type: (String) -> Text
    """
    Convert a header value to text if necessary.
    """
    if isinstance(value, Text):
        return value
    else:
        return value.decode(HEADER_VALUE_ENCODING)


def normalizeHeaderName(name):
    # type: (AnyStr) -> AnyStr
    """
    Normalize a header name.
    """
    return name.lower()


# Internal data representation

def normalizeRawHeaders(headerPairs):
    # type: (Iterable[Iterable[bytes]]) -> Iterable[RawHeader]
    for pair in headerPairs:
        if not isinstance(pair, tuple):
            raise TypeError("header pair must be a tuple")

        try:
            name, value = pair
        except ValueError:
            raise ValueError("header pair must be a 2-tuple")

        if not isinstance(name, bytes):
            raise TypeError("header name must be bytes")
        if not isinstance(value, bytes):
            raise TypeError("header value must be bytes")

        yield (normalizeHeaderName(name), value)


def normalizeRawHeadersFrozen(headerPairs):
    # type: (Iterable[Iterable[bytes]]) -> RawHeaders
    return tuple(normalizeRawHeaders(headerPairs))


def normalizeRawHeadersMutable(headerPairs):
    # type: (Iterable[Iterable[bytes]]) -> MutableRawHeaders
    return list(normalizeRawHeaders(headerPairs))


def getFromRawHeaders(rawHeaders, name):
    # type: (RawHeaders, AnyStr) -> Iterable[AnyStr]
    """
    Get a value from raw headers.
    """
    if isinstance(name, bytes):
        name = normalizeHeaderName(name)
        return (v for n, v in rawHeaders if name == n)

    if isinstance(name, Text):
        rawName = headerNameAsBytes(normalizeHeaderName(name))
        return(
            headerValueAsText(v)
            for n, v in rawHeaders if rawName == n
        )

    raise TypeError("name must be text or bytes")


def rawHeaderName(name):
    # type: (String) -> bytes
    if isinstance(name, bytes):
        return name
    elif isinstance(name, Text):
        return headerNameAsBytes(name)
    else:
        raise TypeError("name must be text or bytes")


def rawHeaderNameAndValue(name, value):
    # type: (String, String) -> Tuple[bytes, bytes]
    if isinstance(name, bytes):
        if not isinstance(value, bytes):
            raise TypeError("value must be bytes to match name")

        return (name, value)
        # rawName  = name   # type: bytes
        # rawValue = value  # type: bytes

    elif isinstance(name, Text):
        if not isinstance(value, Text):
            raise TypeError("value must be text to match name")

        return (headerNameAsBytes(name), headerValueAsBytes(value))
        # rawName  = headerNameAsBytes(name)
        # rawValue = headerValueAsBytes(value)

    else:
        raise TypeError("name must be text or bytes")



# Implementation

@implementer(IHTTPHeaders)
@attrs(frozen=True)
class FrozenHTTPHeaders(object):
    """
    Immutable HTTP entity headers.
    """

    rawHeaders = attrib(
        convert=normalizeRawHeadersFrozen,
        default=(),
    )  # type: RawHeaders


    def getValues(self, name):
        # type: (AnyStr) -> Iterable[AnyStr]
        return getFromRawHeaders(self.rawHeaders, name)



@implementer(IMutableHTTPHeaders)
@attrs(frozen=True)
class MutableHTTPHeaders(object):
    """
    Mutable HTTP entity headers.
    """

    _rawHeaders = attrib(
        convert=normalizeRawHeadersMutable,
        default=(),
    )  # type: MutableRawHeaders


    @property
    def rawHeaders(self):
        # type: () -> RawHeaders
        return tuple(self._rawHeaders)


    def getValues(self, name):
        # type: (AnyStr) -> Iterable[AnyStr]
        return getFromRawHeaders(self._rawHeaders, name)


    def remove(self, name):
        # type: (String) -> None
        rawName = rawHeaderName(name)

        self._rawHeaders[:] = [p for p in self._rawHeaders if p[0] != rawName]


    def addValue(self, name, value):
        # type: (AnyStr, AnyStr) -> None
        self._rawHeaders.append(rawHeaderNameAndValue(name, value))
