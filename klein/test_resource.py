from twisted.trial import unittest

from klein.decorators import expose
from klein.resource import KleinResource

from twisted.internet.defer import succeed, Deferred
from twisted.web import server

from mock import Mock

def requestMock(path, method="GET", host="localhost", port=8080, isSecure=False):
    postpath = path.split('/')

    request = Mock()
    request.getRequestHostname.return_value = host
    request.getHost.return_value.port = port
    request.postpath = postpath
    request.prepath = []
    request.method = method
    request.isSecure.return_value = isSecure
    request.notifyFinish.return_value = Deferred()
    request.finished = False

    def finish():
        request.notifyFinish.return_value.callback(None)
        request.finished = True

    request.finish.side_effect = finish

    return request

def _render(resource, request):
    result = resource.render(request)
    if isinstance(result, str):
        request.write(result)
        request.finish()
        return succeed(None)
    elif result is server.NOT_DONE_YET:
        if request.finished:
            return succeed(None)
        else:
            return request.notifyFinish()
    else:
        raise ValueError("Unexpected return value: %r" % (result,))


class SimpleKlein(KleinResource):
    def __init__(self):
        self.requestsReceived = []
        self.deferred = None

    @expose("/")
    def index(self, request):
        self.requestsReceived.append(request)
        return 'ok'

    @expose("/deferred")
    def deferred(self, request):
        self.requestsReceived.append(request)
        return self.deferred


class KleinResourceTests(unittest.TestCase):
    def test_simpleRouting(self):
        kr = SimpleKlein()

        request = requestMock('/')

        d = _render(kr, request)

        def _cb(result):
            request.write.assert_called_with('ok')
            self.assertEquals(kr.requestsReceived, [request])

        d.addCallback(_cb)

        return d

    def test_deferredRendering(self):
        kr = SimpleKlein()
        kr.deferred = Deferred()

        request = requestMock("/deferred")

        d = _render(kr, request)

        def _cb(result):
            request.write.assert_called_with('ok')
            self.assertEquals(kr.requestsReceived, [request])

        d.addCallback(_cb)
        kr.deferred.callback('ok')

        return d
