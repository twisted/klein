# -*- test-case-name: klein.test.test_request -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
HTTP request.
"""

from attr import Factory, attrib, attrs
from attr.validators import instance_of, optional, provides

from hyperlink import URL

from tubes.itube import IDrain, IFount, ISegment
from tubes.kit import Pauser, beginFlowingTo
from tubes.undefer import fountToDeferred

from twisted.internet.defer import succeed
from twisted.python.compat import nativeString
from twisted.python.failure import Failure
from twisted.web.iweb import IRequest as IWebRequest

from zope.interface import Attribute, Interface, implementer

from ._headers import IHTTPHeaders


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

    method  = Attribute("Request method.")
    uri     = Attribute("Request URI.")
    headers = Attribute("Request entity headers.")


    def bodyAsFount():
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
        """
        The request entity body, as bytes.

        @note: This necessarily reads the entire request body into memory,
            which may be a problem if the body is large (eg. a large upload).

        @note: This method caches the body, which means that unlike
            C{self.bodyAsFount}, calling it repeatedly will return the same
            data.

        @note: This method accesses the fount (via C{self.bodyAsFount}), which
            means the found will not be available afterwards, and that if
            C{self.bodyAsFount} has previously been called directly, this
            method will raise L{NoContentError}.

        @raise NoContentError: If the fount has previously been accessed.
        """



# Simple implementation

@implementer(IHTTPRequest)
@attrs(frozen=True)
class HTTPRequest(object):
    """
    HTTP request.
    """

    method  = attrib(validator=instance_of(str))
    uri     = attrib(validator=instance_of(URL))
    headers = attrib(validator=provides(IHTTPHeaders))


    def bodyAsFount(self):
        raise NotImplementedError()


    def bodyAsBytes(self):
        raise NotImplementedError()



# Support for L{twisted.web.iweb.IRequest}

@implementer(IHTTPRequest)
@attrs(frozen=True)
class HTTPRequestFromIRequest(object):
    """
    HTTP request.

    This is an L{IHTTPRequest} implementation that wraps a
    L{twisted.web.iweb.IRequest} object.

    This is used by Klein to expose "legacy" request objects from
    L{twisted.web} to clients while presenting the new interface.
    """

    @attrs(frozen=False)
    class _State(object):
        """
        Internal mutable state for L{HTTPRequestFromIRequest}.
        """

        _cachedBody = attrib(
            validator=optional(instance_of(bytes)), default=None, init=False
        )

    _request = attrib(validator=provides(IWebRequest))
    _state = attrib(default=Factory(_State), init=False)


    @property
    def method(self):
        return self._request.method.decode("ascii")


    @property
    def uri(self):
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
        raise NotImplementedError()


    def bodyAsFount(self):
        source = self._request.content
        if source is None:
            raise NoContentError()

        fount = _IOFount(source=source)

        self._request.content = None

        return fount


    def bodyAsBytes(self):
        if self._state._cachedBody is not None:
            return succeed(self._state._cachedBody)

        def collect(chunks):
            bodyBytes = b"".join(chunks)
            self._state._cachedBody = bodyBytes
            return bodyBytes

        d = fountToDeferred(self.bodyAsFount())
        d.addCallback(collect)
        return d



# FIXME: move this to tubes.
# FIXME: this should stream.
@implementer(IFount)
@attrs(frozen=False)
class _IOFount(object):
    """
    Fount that reads from a file-like-object.
    """

    outputType = ISegment

    _source = attrib()

    drain = attrib(
        validator=optional(provides(IDrain)), default=None, init=False
    )
    _paused = attrib(validator=instance_of(bool), default=False, init=False)


    def __attrs_post_init__(self):
        self._pauser = Pauser(self._pause, self._resume)


    def _flowToDrain(self):
        if self.drain is not None and not self._paused:
            data = self._source.read()
            if data:
                self.drain.receive(data)
            self.drain.flowStopped(Failure(StopIteration()))


    def flowTo(self, drain):
        result = beginFlowingTo(self, drain)
        self._flowToDrain()
        return result


    def pauseFlow(self):
        return self._pauser.pause()


    def stopFlow(self):
        return self._pauser.resume()


    def _pause(self):
        self._paused = True


    def _resume(self):
        self._paused = False
        self._flowToDrain()
