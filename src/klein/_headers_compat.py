# -*- test-case-name: klein.test.test_headers -*-
# Copyright (c) 2011-2021. See LICENSE for details.

"""
Support for interoperability with L{twisted.web.http_headers.Headers}.
"""

from typing import AnyStr, Iterable, Tuple, cast

from attr import attrib, attrs
from attr.validators import instance_of
from zope.interface import implementer

from twisted.web.http_headers import Headers

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
class HTTPHeadersWrappingHeaders:
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
            # typing note: getRawHeaders is typed to return an optional even if
            # default is not None. We could assert not None, but are casting
            # here so that if the hints for getRawHeaders are fixed later,
            # mypy will tell us to remove the useless cast.
            values = cast(
                Iterable[str],
                self._headers.getRawHeaders(
                    headerNameAsBytes(name), default=()
                ),
            )
            values = (headerValueAsText(value) for value in values)
        else:
            raise TypeError(f"name {name!r} must be str or bytes")

        return values

    def remove(self, name: String) -> None:
        self._headers.removeHeader(rawHeaderName(name))

    def addValue(self, name: AnyStr, value: AnyStr) -> None:
        rawName, rawValue = rawHeaderNameAndValue(name, value)

        self._headers.addRawHeader(rawName, rawValue)
