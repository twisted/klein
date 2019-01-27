# -*- test-case-name: klein.test.test_irequest -*-
# Copyright (c) 2017-2018. See LICENSE for details.

"""
Support for interoperability with L{twisted.web.iweb.IRequest}.
"""

from io import BytesIO
from typing import Text

from attr import Factory, attrib, attrs
from attr.validators import provides

from hyperlink import DecodedURL

from tubes.itube import IFount

from twisted.internet.defer import Deferred, succeed
from twisted.python.compat import nativeString
from twisted.web.iweb import IRequest

from zope.interface import implementer

from ._headers import IHTTPHeaders
from ._headers_compat import HTTPHeadersWrappingHeaders
from ._message import FountAlreadyAccessedError, MessageState
from ._request import IHTTPRequest
from ._tubes import IOFount, fountToBytes

# Silence linter
Deferred, IFount, IHTTPHeaders, Text


__all__ = ()


noneIO = BytesIO()



@implementer(IHTTPRequest)
@attrs(frozen=True)
class HTTPRequestWrappingIRequest(object):
    """
    HTTP request.

    This is an L{IHTTPRequest} implementation that wraps an L{IRequest} object.
    """

    _request = attrib(validator=provides(IRequest))  # type: IRequest

    _state = attrib(
        default=Factory(MessageState), init=False
    )  # type: MessageState


    @property
    def method(self):
        # type: () -> Text
        return self._request.method.decode("ascii")


    @property
    def uri(self):
        # type: () -> DecodedURL
        request = self._request

        # This code borrows from t.w.server.Request._prePathURL.

        if request.isSecure():
            scheme = u"https"
        else:
            scheme = u"http"

        netloc = nativeString(request.getRequestHostname())

        port = request.getHost().port
        if request.isSecure():
            default = 443
        else:
            default = 80
        if port != default:
            netloc += u":{}".format(port)

        path = nativeString(request.uri)
        if path and path[0] == u"/":
            path = path[1:]

        return DecodedURL.fromText(u"{}://{}/{}".format(scheme, netloc, path))


    @property
    def headers(self):
        # type: () -> IHTTPHeaders
        return HTTPHeadersWrappingHeaders(headers=self._request.requestHeaders)


    def bodyAsFount(self):
        # type: () -> IFount
        source = self._request.content
        if source is noneIO:
            raise FountAlreadyAccessedError()

        fount = IOFount(source=source)

        self._request.content = noneIO

        return fount


    def bodyAsBytes(self):
        # type: () -> Deferred[bytes]
        if self._state.cachedBody is not None:
            return succeed(self._state.cachedBody)

        def cache(bodyBytes):
            # type: (bytes) -> bytes
            self._state.cachedBody = bodyBytes
            return bodyBytes

        fount = self.bodyAsFount()
        d = fountToBytes(fount)
        d.addCallback(cache)
        return d
