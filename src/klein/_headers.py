# -*- test-case-name: klein.test.test_request -*-
# Copyright (c) 2011-2021. See LICENSE for details.

"""
HTTP headers API.
"""

from typing import AnyStr, Iterable, Tuple, Union

from attr import Factory, attrib, attrs
from zope.interface import implementer

from ._imessage import (
    IHTTPHeaders,
    IMutableHTTPHeaders,
    MutableRawHeaders,
    RawHeader,
    RawHeaders,
)


__all__ = ()


String = Union[bytes, str]


# Encoding/decoding header data

HEADER_NAME_ENCODING = "iso-8859-1"
HEADER_VALUE_ENCODING = "iso-8859-1"


def headerNameAsBytes(name: String) -> bytes:
    """
    Convert a header name to bytes if necessary.
    """
    if isinstance(name, bytes):
        return name
    else:
        return name.encode(HEADER_NAME_ENCODING)


def headerNameAsText(name: String) -> str:
    """
    Convert a header name to str if necessary.
    """
    if isinstance(name, str):
        return name
    else:
        return name.decode(HEADER_NAME_ENCODING)


def headerValueAsBytes(value: String) -> bytes:
    """
    Convert a header value to bytes if necessary.
    """
    if isinstance(value, bytes):
        return value
    else:
        return value.encode(HEADER_VALUE_ENCODING)


def headerValueAsText(value: String) -> str:
    """
    Convert a header value to str if necessary.
    """
    if isinstance(value, str):
        return value
    else:
        return value.decode(HEADER_VALUE_ENCODING)


def normalizeHeaderName(name: AnyStr) -> AnyStr:
    """
    Normalize a header name.
    """
    return name.lower()


# Internal data representation


def normalizeRawHeaders(
    headerPairs: Iterable[Iterable[String]],
) -> Iterable[RawHeader]:
    for pair in headerPairs:
        try:
            name, value = pair
        except ValueError:
            raise ValueError("header pair must be a 2-item iterable")

        name = normalizeHeaderName(headerNameAsBytes(name))
        value = headerValueAsBytes(value)

        yield (normalizeHeaderName(name), value)


def normalizeRawHeadersFrozen(
    headerPairs: Iterable[Iterable[bytes]],
) -> RawHeaders:
    return tuple(normalizeRawHeaders(headerPairs))


def normalizeRawHeadersMutable(
    headerPairs: Iterable[Iterable[bytes]],
) -> MutableRawHeaders:
    return list(normalizeRawHeaders(headerPairs))


def getFromRawHeaders(rawHeaders: RawHeaders, name: AnyStr) -> Iterable[AnyStr]:
    """
    Get a value from raw headers.
    """
    if isinstance(name, bytes):
        name = normalizeHeaderName(name)
        return (v for n, v in rawHeaders if name == n)

    if isinstance(name, str):
        rawName = headerNameAsBytes(normalizeHeaderName(name))
        return (headerValueAsText(v) for n, v in rawHeaders if rawName == n)

    raise TypeError(f"name {name!r} must be str or bytes")


def rawHeaderName(name: String) -> bytes:
    if isinstance(name, bytes):
        return name
    elif isinstance(name, str):
        return headerNameAsBytes(name)
    else:
        raise TypeError(f"name {name!r} must be str or bytes")


def rawHeaderNameAndValue(name: String, value: String) -> Tuple[bytes, bytes]:
    if isinstance(name, bytes):
        if not isinstance(value, bytes):
            raise TypeError(
                "value {!r} must be bytes to match name {!r}".format(
                    value, name
                )
            )
        return (name, value)

    elif isinstance(name, str):
        if not isinstance(value, str):
            raise TypeError(
                f"value {value!r} must be str to match name {name!r}"
            )
        return (headerNameAsBytes(name), headerValueAsBytes(value))

    else:
        raise TypeError(f"name {name!r} must be str or bytes")


# Implementation


@implementer(IHTTPHeaders)
@attrs(frozen=True)
class FrozenHTTPHeaders:
    """
    Immutable HTTP entity headers.
    """

    rawHeaders: RawHeaders = attrib(
        converter=normalizeRawHeadersFrozen,
        default=(),
    )

    def getValues(self, name: AnyStr) -> Iterable[AnyStr]:
        return getFromRawHeaders(self.rawHeaders, name)


@implementer(IMutableHTTPHeaders)
@attrs(frozen=True)
class MutableHTTPHeaders:
    """
    Mutable HTTP entity headers.
    """

    _rawHeaders: MutableRawHeaders = attrib(
        converter=normalizeRawHeadersMutable,
        default=Factory(list),
    )

    @property
    def rawHeaders(self) -> RawHeaders:
        return tuple(self._rawHeaders)

    def getValues(self, name: AnyStr) -> Iterable[AnyStr]:
        return getFromRawHeaders(self._rawHeaders, name)

    def remove(self, name: String) -> None:
        rawName = rawHeaderName(name)

        self._rawHeaders[:] = [p for p in self._rawHeaders if p[0] != rawName]

    def addValue(self, name: AnyStr, value: AnyStr) -> None:
        self._rawHeaders.append(rawHeaderNameAndValue(name, value))
