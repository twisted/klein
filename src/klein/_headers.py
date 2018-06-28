# -*- test-case-name: klein.test.test_request -*-
# Copyright (c) 2017-2018. See LICENSE for details.

"""
HTTP headers API.
"""

from typing import AnyStr, Iterable, Text, Tuple, Union

from attr import Factory, attrib, attrs

from zope.interface import implementer

from ._imessage import MutableRawHeaders, RawHeader, RawHeaders
from ._interfaces import IHTTPHeaders, IMutableHTTPHeaders

# Silence linter
AnyStr, Iterable, Tuple, MutableRawHeaders, RawHeader, RawHeaders


__all__ = ()


String = Union[bytes, Text]


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
    # type: (Iterable[Iterable[String]]) -> Iterable[RawHeader]
    for pair in headerPairs:
        try:
            name, value = pair
        except ValueError:
            raise ValueError("header pair must be a 2-item iterable")

        name = normalizeHeaderName(headerNameAsBytes(name))
        value = headerValueAsBytes(value)

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

    raise TypeError("name {!r} must be text or bytes".format(name))


def rawHeaderName(name):
    # type: (String) -> bytes
    if isinstance(name, bytes):
        return name
    elif isinstance(name, Text):
        return headerNameAsBytes(name)
    else:
        raise TypeError("name {!r} must be text or bytes".format(name))


def rawHeaderNameAndValue(name, value):
    # type: (String, String) -> Tuple[bytes, bytes]
    if isinstance(name, bytes):
        if not isinstance(value, bytes):
            raise TypeError(
                "value {!r} must be bytes to match name {!r}"
                .format(value, name)
            )
        return (name, value)

    elif isinstance(name, Text):
        if not isinstance(value, Text):
            raise TypeError(
                "value {!r} must be text to match name {!r}"
                .format(value, name)
            )
        return (headerNameAsBytes(name), headerValueAsBytes(value))

    else:
        raise TypeError("name {!r} must be text or bytes".format(name))



# Implementation

@implementer(IHTTPHeaders)
@attrs(frozen=True)
class FrozenHTTPHeaders(object):
    """
    Immutable HTTP entity headers.
    """

    rawHeaders = attrib(
        converter=normalizeRawHeadersFrozen,
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
        converter=normalizeRawHeadersMutable,
        default=Factory(list),
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
