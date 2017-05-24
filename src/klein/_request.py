# -*- test-case-name: klein.test.test_request -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
HTTP request.
"""

from attr import attrib, attrs
from attr.validators import instance_of, optional, provides

from hyperlink import URL

from tubes.itube import IDrain, IFount, ISegment
from tubes.kit import Pauser
# from tubes.undefer import fountToDeferred

from twisted.python.compat import unicode
from twisted.python.failure import Failure
from twisted.web.iweb import IRequest as IWebRequest

from zope.interface import implementer


__all__ = (
    "NoContentError",
    "HTTPRequest",
)



class NoContentError(Exception):
    """
    Request has no content.
    This implies someone already accessed the body fount.
    """



# FIXME: move this to tubes.  Also: make it stream.
@implementer(IFount)
@attrs()
class IOFount(object):
    """
    Fount that reads from a file-like-object.
    """

    outputType = ISegment

    _input = attrib()

    drain = attrib(
        validator=optional(provides(IDrain)), default=None, init=False
    )
    _paused = attrib(validator=instance_of(bool), default=False, init=False)


    def __attrs_post_init__(self):
        self._pauser = Pauser(self._pause, self._resume)


    def _flowToDrain(self):
        if self.drain is not None and not self._paused:
            data = self._input.read()
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



@attrs(frozen=True)
class HTTPRequest(object):
    """
    HTTP request.
    """

    _request = attrib(validator=provides(IWebRequest))

    _content = attrib(
        validator=optional(instance_of(bytes)), default=None, init=False
    )


    @property
    def method(self):
        return self._request.method.decode("ascii")


    @property
    def url(self):
        request = self._request

        # This code borrows from t.w.server.Request._prePathURL.

        if request.isSecure():
            scheme = u"https"
        else:
            scheme = u"http"

        netloc = request.getRequestHostname()

        port = request.getHost().port
        if request.isSecure():
            default = 443
        else:
            default = 80
        if port != default:
            netloc += u":{}".format(port)

        path = request.uri
        if path and path[0] == "/":
            path = path[1:]

        return URL.fromText(u"{}://{}/{}".format(scheme, netloc, path))


    # headers = attrib(validator=instance_of(Headers))


    def bodyFount(self):
        input = _request.content

        if input is None:
            raise NoContentError()

        fount = IOFount(input)

        _request.content = None


    def bodyBytes(self):
        if self._content is not None:
            return self._content

        fount = self.bodyFount()

        def collect(chunks):
            content = b"".join(chunks)
            self._content = content

        d = fountToDeferred(self.bodyFount())
        d.addCallback(collect)
