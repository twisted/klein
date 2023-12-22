"""
Dependency-Injected HTTP metadata.
"""

from typing import Any, Dict, Mapping, Sequence, Type, Union, cast

import attr
from hyperlink import DecodedURL
from zope.interface import Interface, implementer, provider

from twisted.python.components import Componentized
from twisted.web.iweb import IRequest

from .interfaces import (
    IDependencyInjector,
    IRequestLifecycle,
    IRequiredParameter,
)


def urlFromRequest(request: IRequest) -> DecodedURL:
    sentHeader = request.getHeader(b"host")
    if sentHeader is not None:
        sentHeader = sentHeader.decode("charmap")
        if ":" in sentHeader:
            host, port = sentHeader.split(":")
            port = int(port)
        else:
            host = sentHeader
            port = None
    else:
        client = request.client  # type: ignore[attr-defined]
        host = client.host
        port = client.port

    url = DecodedURL.fromText(request.uri.decode("charmap"))
    url = url.replace(
        scheme="https" if request.isSecure() else "http",
        host=host,
        port=port,
    )
    return url


@provider(IRequiredParameter, IDependencyInjector)
class RequestURL:
    """
    Require a hyperlink L{DecodedURL} object from a L{Requirer}.

    @since: Klein NEXT
    """

    @classmethod
    def registerInjector(
        cls,
        injectionComponents: Componentized,
        parameterName: str,
        requestLifecycle: IRequestLifecycle,
    ) -> IDependencyInjector:
        # typing note: https://github.com/Shoobx/mypy-zope/issues/39
        return cast(IDependencyInjector, cls())

    @classmethod
    def injectValue(
        cls,
        instance: Any,
        request: IRequest,
        routeParams: Dict[str, Any],
    ) -> DecodedURL:
        return urlFromRequest(request)

    @classmethod
    def finalize(cls) -> None:
        "Nothing to do upon finalization."


@implementer(IRequiredParameter, IDependencyInjector)
@attr.frozen
class RequestComponent:
    """
    Require a hyperlink L{DecodedURL} object from a L{Requirer}.

    @since: Klein NEXT
    """

    interface: Type[Interface]

    def registerInjector(
        self,
        injectionComponents: Componentized,
        parameterName: str,
        requestLifecycle: IRequestLifecycle,
    ) -> IDependencyInjector:
        return self

    def injectValue(
        self, instance: Any, request: IRequest, routeParams: Dict[str, Any]
    ) -> DecodedURL:
        return cast(
            DecodedURL,
            cast(Componentized, request).getComponent(self.interface),
        )

    def finalize(cls) -> None:
        "Nothing to do upon finalization."


@attr.s(auto_attribs=True, frozen=True)
class Response:
    """
    Metadata about an HTTP response, with an object that Klein knows how to
    understand.

    This includes:

        - an HTTP response code

        - some HTTP headers

        - a body object, which can be anything else Klein understands; for
          example, an IResource, an IRenderable, str, bytes, etc.

    @since: Klein NEXT
    """

    code: int = 200
    headers: Mapping[
        Union[str, bytes], Union[str, bytes, Sequence[Union[str, bytes]]]
    ] = attr.ib(factory=dict)
    body: Any = ""

    def _applyToRequest(self, request: IRequest) -> Any:
        """
        Apply this L{Response} to the given L{IRequest}, setting its response
        code and headers.

        Private because:

            - this should only ever be applied by Klein, and

            - hopefully someday soon this will be replaced with something that
              actually creates a txrequest-style response object.
        """
        request.setResponseCode(self.code)
        for headerName, headerValueOrValues in self.headers.items():
            if not isinstance(headerValueOrValues, (str, bytes)):
                headerValues = headerValueOrValues
            else:
                headerValues = [headerValueOrValues]
            request.responseHeaders.setRawHeaders(headerName, headerValues)
        return self.body
