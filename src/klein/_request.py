# -*- test-case-name: klein.test.test_request -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
HTTP request API.
"""

from io import BytesIO
from typing import Any, Iterable, Text, Union
from typing.io import BinaryIO

from attr import Factory, attrib, attrs
from attr.validators import instance_of, optional, provides

from hyperlink import URL

from tubes.itube import IDrain, IFount, ISegment
from tubes.kit import Pauser, beginFlowingTo
from tubes.undefer import fountToDeferred

from twisted.internet.defer import Deferred, succeed
from twisted.python.compat import nativeString
from twisted.python.failure import Failure
from twisted.web.iweb import IRequest

from zope.interface import Attribute, Interface, implementer

from ._headers import (
    FrozenHTTPHeaders, HTTPHeadersFromHeaders, IHTTPHeaders
)

Any, BinaryIO, Deferred, IHTTPHeaders, Iterable, Text, Union  # Silence linter


__all__ = ()



# Interfaces

class NoContentError(Exception):
    """
    Request has no content.
    This implies someone already accessed the body fount.
    """



class IHTTPRequest(Interface):
    """
    HTTP request.
    """

    method  = Attribute("Request method.")          # type: Text
    uri     = Attribute("Request URI.")             # type: URL
    headers = Attribute("Request entity headers.")  # type: IHTTPHeaders


    def bodyAsFount():
        # type: () -> IFount
        """
        The request entity body, as a fount.

        @note: The fount may only be accessed once.
            It provides a mechanism for accessing the body as a stream of data,
            potentially as it is read from the network, without having to cache
            the entire body, which may be large.
            Because there is no caching, it is not possible to "start over" by
            accessing the fount a second time.
            Attempting to do so will raise L{NoContentError}.

        @raise NoContentError: If the fount has previously been accessed.
        """


    def bodyAsBytes():
        # type: () -> Deferred[bytes]
        """
        The request entity body, as bytes.

        @note: This necessarily reads the entire request body into memory,
            which may be a problem if the body is large (eg. a large upload).

        @note: This method caches the body, which means that unlike
            C{self.bodyAsFount}, calling it repeatedly will return the same
            data.

        @note: This method accesses the fount (via C{self.bodyAsFount}), which
            means the fount will not be available afterwards, and that if
            C{self.bodyAsFount} has previously been called directly, this
            method will raise L{NoContentError}.

        @raise NoContentError: If the fount has previously been accessed.
        """



# Simple implementation

def validateBody(instance, attribute, body):
    # type: (Any, Any, Union[bytes, IFount]) -> None
    if (
        type(body) is not bytes and
        not IFount.providedBy(body)
    ):
        raise TypeError("body must be bytes or IFount")


@implementer(IHTTPRequest)
@attrs(frozen=True)
class FrozenHTTPRequest(object):
    """
    Immutable HTTP request.
    """

    @attrs(frozen=False)
    class _State(object):
        """
        Internal mutable state for L{HTTPRequestFromIRequest}.
        """

        _cachedBody = attrib(
            validator=optional(instance_of(bytes)), default=None, init=False
        )  # type: bytes

    method  = attrib(validator=instance_of(Text))  # type: Text
    uri     = attrib(validator=instance_of(URL))  # type: URL
    headers = attrib(
        validator=instance_of(FrozenHTTPHeaders)
    )  # type: FrozenHTTPHeaders

    _body = attrib(validator=validateBody)  # type: Union[bytes, IFount]

    _state = attrib(default=Factory(_State), init=False)  # type: _State


    def bodyAsFount(self):
        # type: () -> IFount
        if type(self._body) is bytes:
            return bytesToFount(self._body)

        # assuming: IFount.providedBy(self._body)

        return self._body


    def bodyAsBytes(self):
        # type: () -> bytes
        if type(self._body) is bytes:
            return succeed(self._body)

        # assuming: IFount.providedBy(self._body)

        def cache(bodyBytes):
            # type: (bytes) -> bytes
            self._state._cachedBody = bodyBytes
            return bodyBytes

        d = fountToBytes(self._body)
        d.addCallback(cache)
        return d



# Support for L{IRequest}

@implementer(IHTTPRequest)
@attrs(frozen=True)
class HTTPRequestFromIRequest(object):
    """
    HTTP request.

    This is an L{IHTTPRequest} implementation that wraps an L{IRequest} object.

    This is used by Klein to expose objects from L{twisted.web} to clients
    while presenting the Klein interface.
    """

    @attrs(frozen=False)
    class _State(object):
        """
        Internal mutable state for L{HTTPRequestFromIRequest}.
        """

        _cachedBody = attrib(
            validator=optional(instance_of(bytes)), default=None, init=False
        )  # type: bytes

    _request = attrib(validator=provides(IRequest))       # type: IRequest

    _state = attrib(default=Factory(_State), init=False)  # type: _State


    @property
    def method(self):
        # type: () -> Text
        return self._request.method.decode("ascii")


    @property
    def uri(self):
        # type: () -> URL
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

        return URL.fromText(u"{}://{}/{}".format(scheme, netloc, path))


    @property
    def headers(self):
        # type: () -> IHTTPHeaders
        return HTTPHeadersFromHeaders(headers=self._request.requestHeaders)


    def bodyAsFount(self):
        # type: () -> IFount
        source = self._request.content
        if source is None:
            raise NoContentError()

        fount = IOFount(source=source)

        self._request.content = None

        return fount


    def bodyAsBytes(self):
        # type: () -> bytes
        if self._state._cachedBody is not None:
            return succeed(self._state._cachedBody)

        def cache(bodyBytes):
            self._state._cachedBody = bodyBytes
            return bodyBytes

        fount = self.bodyAsFount()
        d = fountToBytes(fount)
        d.addCallback(cache)
        return d



# Fount-related utilities that probably should live in tubes.

# See https://github.com/twisted/tubes/issues/60
def fountToBytes(fount):
    # type: (IFount) -> Deferred[bytes]
    def collect(chunks):
        # type: (Iterable[bytes]) -> bytes
        return b"".join(chunks)

    d = fountToDeferred(fount)
    d.addCallback(collect)
    return d


# See https://github.com/twisted/tubes/issues/60
def bytesToFount(data):
    # type: (bytes) -> IFount
    # FIXME: This seems rather round-about
    return IOFount(source=BytesIO(data))



# https://github.com/twisted/tubes/issues/61
@implementer(IFount)
@attrs(frozen=False)
class IOFount(object):
    """
    Fount that reads from a file-like-object.
    """

    outputType = ISegment

    _source = attrib()  # type: BinaryIO

    drain = attrib(
        validator=optional(provides(IDrain)), default=None, init=False
    )  # type: IDrain
    _paused = attrib(validator=instance_of(bool), default=False, init=False)


    def __attrs_post_init__(self):
        # type: () -> None
        self._pauser = Pauser(self._pause, self._resume)


    def _flowToDrain(self):
        # type: () -> None
        if self.drain is not None and not self._paused:
            data = self._source.read()
            if data:
                self.drain.receive(data)
            self.drain.flowStopped(Failure(StopIteration()))


    # FIXME: this should stream.
    def flowTo(self, drain):
        # type: (IDrain) -> IFount
        result = beginFlowingTo(self, drain)
        self._flowToDrain()
        return result


    def pauseFlow(self):
        # type: () -> None
        return self._pauser.pause()


    def stopFlow(self):
        # type: () -> None
        return self._pauser.resume()


    def _pause(self):
        # type: () -> None
        self._paused = True


    def _resume(self):
        # type: () -> None
        self._paused = False
        self._flowToDrain()
