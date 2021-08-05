# -*- test-case-name: klein.test.test_irequest -*-
# Copyright (c) 2011-2021. See LICENSE for details.

"""
Support for interoperability with L{twisted.web.iweb.IRequest}.
"""

from io import BytesIO
from typing import cast

from attr import Factory, attrib, attrs
from attr.validators import provides
from hyperlink import DecodedURL
from tubes.itube import IFount
from zope.interface import implementer

from twisted.python.compat import nativeString
from twisted.web.iweb import IRequest

from ._headers import IHTTPHeaders
from ._headers_compat import HTTPHeadersWrappingHeaders
from ._message import FountAlreadyAccessedError, MessageState
from ._request import IHTTPRequest
from ._tubes import IOFount, fountToBytes


__all__ = ()


noneIO = BytesIO()


@implementer(IHTTPRequest)
@attrs(frozen=True)
class HTTPRequestWrappingIRequest:
    """
    HTTP request.

    This is an L{IHTTPRequest} implementation that wraps an L{IRequest} object.
    """

    _request: IRequest = attrib(validator=provides(IRequest))

    _state: MessageState = attrib(default=Factory(MessageState), init=False)

    @property
    def method(self) -> str:
        return cast(str, self._request.method.decode("ascii"))

    @property
    def uri(self) -> DecodedURL:
        request = self._request

        # This code borrows from t.w.server.Request._prePathURL.

        if request.isSecure():
            scheme = "https"
        else:
            scheme = "http"

        netloc = nativeString(request.getRequestHostname())

        port = request.getHost().port
        if request.isSecure():
            default = 443
        else:
            default = 80
        if port != default:
            netloc += f":{port}"

        path = nativeString(request.uri)
        if path and path[0] == "/":
            path = path[1:]

        return DecodedURL.fromText(f"{scheme}://{netloc}/{path}")

    @property
    def headers(self) -> IHTTPHeaders:
        return HTTPHeadersWrappingHeaders(headers=self._request.requestHeaders)

    def bodyAsFount(self) -> IFount:
        source = self._request.content
        if source is noneIO:
            raise FountAlreadyAccessedError()

        fount = IOFount(source=source)

        self._request.content = noneIO

        return fount

    async def bodyAsBytes(self) -> bytes:
        if self._state.cachedBody is not None:
            return self._state.cachedBody  # pragma: no cover

        fount = self.bodyAsFount()
        self._state.cachedBody = await fountToBytes(fount)
        return self._state.cachedBody
