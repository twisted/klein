
"""
Dependency-Injected HTTP metadata.
"""

import attr
from six import text_type
from hyperlink import parse
from typing import TYPE_CHECKING, Union, Text, Mapping, Sequence, Any
from klein.interfaces import IRequiredParameter, IDependencyInjector
from zope.interface import provider, implementer
from zope.interface.interfaces import IInterface

if TYPE_CHECKING:               # pragma: no cover
    from hyperlink import DecodedURL
    from twisted.web.iweb import IRequest
    DecodedURL, IRequest

def urlFromRequest(request):
    # type: (IRequest) -> DecodedURL
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
        host = request.client.host
        port = request.client.port

    return parse(request.uri.decode("charmap")).replace(
        scheme="https" if request.isSecure() else "http",
        host=host,
        port=port,
    )


@provider(IRequiredParameter, IDependencyInjector)
class RequestURL(object):
    """
    Require a hyperlink L{DecodedURL} object from a L{Requirer}.

    @since: Klein NEXT
    """

    @classmethod
    def registerInjector(cls, injectionComponents, parameterName,
                         requestLifecycle):
        # type: (Componentized, str, IRequestLifecycle) -> IDependencyInjector
        return cls()

    @classmethod
    def injectValue(cls, instance, request, routeParams):
        # type: (Any, IRequest, Dict[str, Any]) -> DecodedURL
        return urlFromRequest(request)

    @classmethod
    def finalize(cls):
        # type: () -> None
        "Nothing to do upon finalization."



@implementer(IRequiredParameter, IDependencyInjector)
@attr.s(frozen=True)
class RequestComponent(object):
    """
    Require a hyperlink L{DecodedURL} object from a L{Requirer}.

    @since: Klein NEXT
    """

    interface = attr.ib(type=IInterface)

    def registerInjector(self, injectionComponents, parameterName,
                         requestLifecycle):
        # type: (Componentized, str, IRequestLifecycle) -> IDependencyInjector
        return self

    def injectValue(self, instance, request, routeParams):
        # type: (Any, IRequest, Dict[str, Any]) -> DecodedURL
        return request.getComponent(self.interface)

    def finalize(cls):
        # type: () -> None
        "Nothing to do upon finalization."




@attr.s(frozen=True)
class Response(object):
    """
    Metadata about an HTTP response, with an object that Klein knows how to
    understand.

    This includes:

        - an HTTP response code

        - some HTTP headers

        - a body object, which can be anything else Klein understands; for
          example, an IResource, an IRenderable, text, bytes, etc.

    @since: Klein NEXT
    """
    code = attr.ib(type=int, default=200)
    headers = attr.ib(
        type=Mapping[Union[Text, bytes], Union[Text, bytes,
                                               Sequence[Union[Text, bytes]]]],
        default=attr.Factory(dict),
    )
    body = attr.ib(type=Any, default=u'')

    def _applyToRequest(self, request):
        # type: (IRequest) -> Any
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
            if isinstance(headerValueOrValues, (text_type, bytes)):
                headerValues = [headerValueOrValues]
            else:
                headerValues = headerValueOrValues
            request.setRawHeaders(headerName, headerValues)
        return self.body

