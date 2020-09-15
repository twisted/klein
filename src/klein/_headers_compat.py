# -*- test-case-name: klein.test.test_headers -*-
# Copyright (c) 2011-2019. See LICENSE for details.

"""
Support for interoperability with L{twisted.web.http_headers.Headers}.
"""

from typing import AnyStr, Iterable, Tuple, cast

from attr import attrib, attrs
from attr.validators import instance_of

from twisted.web.http_headers import Headers

from zope.interface import implementer

from ._headers import (
    IMutableHTTPHeaders,
    RawHeaders,
    String,
    headerNameAsBytes,
    headerValueAsText,
    normalizeHeaderName,
    rawHeaderName,
    rawHeaderNameAndValue,
)


__all__ = ()


@implementer(IMutableHTTPHeaders)
@attrs(frozen=True)
class HTTPHeadersWrappingHeaders(object):
    """
    HTTP entity headers.

    This is an L{IMutableHTTPHeaders} implementation that wraps a L{Headers}
    object.
    """

    # NOTE: In case Headers has different ideas about encoding text than we do,
    # always interact with it using bytes, not str.

    _headers: Headers = attrib(validator=instance_of(Headers))

    @property
    def rawHeaders(self) -> RawHeaders:
        def pairs() -> Iterable[Tuple[bytes, bytes]]:
            for name, values in self._headers.getAllRawHeaders():
                name = normalizeHeaderName(name)
                for value in values:
                    yield (name, value)

        return tuple(pairs())

    def getValues(self, name: AnyStr) -> Iterable[AnyStr]:
        if isinstance(name, bytes):
            values = cast(
                Iterable[AnyStr], self._headers.getRawHeaders(name, default=())
            )
        elif isinstance(name, str):
            values = (
                headerValueAsText(value)
                for value in self._headers.getRawHeaders(
                    headerNameAsBytes(name), default=()
                )
            )
        else:
            raise TypeError(f"name {name!r} must be str or bytes")

        return values

    def remove(self, name: String) -> None:
        self._headers.removeHeader(rawHeaderName(name))

    def addValue(self, name: AnyStr, value: AnyStr) -> None:
        rawName, rawValue = rawHeaderNameAndValue(name, value)

        self._headers.addRawHeader(rawName, rawValue)
