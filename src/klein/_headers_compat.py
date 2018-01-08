# -*- test-case-name: klein.test.test_headers -*-
# Copyright (c) 2017-2018. See LICENSE for details.

"""
Support for interoperability with L{twisted.web.http_headers.Headers}.
"""

from typing import AnyStr, Iterable, Text, Tuple

from attr import attrib, attrs
from attr.validators import instance_of

from twisted.web.http_headers import Headers

from zope.interface import implementer

from ._headers import (
    IMutableHTTPHeaders, RawHeaders, String, headerNameAsBytes,
    headerValueAsText, normalizeHeaderName, rawHeaderName,
    rawHeaderNameAndValue,
)

AnyStr, Iterable, RawHeaders, String, Tuple  # Silence linter


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
    # always interact with it using bytes, not text.

    _headers = attrib(validator=instance_of(Headers))  # type: Headers


    @property
    def rawHeaders(self):
        # type: () -> RawHeaders
        def pairs():
            # type: () -> Iterable[Tuple[bytes, bytes]]
            for name, values in self._headers.getAllRawHeaders():
                name = normalizeHeaderName(name)
                for value in values:
                    yield (name, value)

        return tuple(pairs())


    def getValues(self, name):
        # type: (AnyStr) -> Iterable[AnyStr]
        if isinstance(name, bytes):
            values = self._headers.getRawHeaders(name, default=())
        elif isinstance(name, Text):
            values = (
                headerValueAsText(value)
                for value in self._headers.getRawHeaders(
                    headerNameAsBytes(name), default=()
                )
            )
        else:
            raise TypeError("name {!r} must be text or bytes".format(name))

        return values


    def remove(self, name):
        # type: (String) -> None
        self._headers.removeHeader(rawHeaderName(name))


    def addValue(self, name, value):
        # type: (AnyStr, AnyStr) -> None
        rawName, rawValue = rawHeaderNameAndValue(name, value)

        self._headers.addRawHeader(rawName, rawValue)
