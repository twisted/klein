from twisted.trial import unittest

from klein.decorators import expose
from klein.resource import KleinResource

from twisted.internet.defer import succeed, Deferred
from twisted.web import server

from twisted.web.template import Element, XMLString, renderer

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


class SimpleElement(Element):
    loader = XMLString("""
    <h1 xmlns:t="http://twistedmatrix.com/ns/twisted.web.template/0.1" t:render="name" />
    """)

    def __init__(self, name):
        self._name = name

    @renderer
    def name(self, request, tag):
        return tag(self._name)


class SimpleKlein(KleinResource):
    def __init__(self):
        self.deferred = None

    @expose("/")
    def index(self, request):
        return 'ok'

    @expose("/trivial")
    def trivial(self, request):
        return "trivial"

    @expose("/deferred")
    def deferred(self, request):
        return self.deferred

    @expose("/element/<string:name>")
    def element(self, request, name):
        return SimpleElement(name)


class ChildOfKlein(SimpleKlein):

    @expose("/")
    def index(self, request):
        return "child"


class KleinResourceTests(unittest.TestCase):
    def test_simpleRouting(self):
        kr = SimpleKlein()

        request = requestMock('/')

        d = _render(kr, request)

        def _cb(result):
            request.write.assert_called_with('ok')

        d.addCallback(_cb)

        return d

    def test_inheritedRouting(self):
        kr = ChildOfKlein()

        request = requestMock("/trivial")

        d = _render(kr, request)

        @d.addCallback
        def _cb(result):
            request.write.assert_called_with('trivial')

        return d

    def test_inheritedOverride(self):
        kr = ChildOfKlein()

        request = requestMock("/")

        d = _render(kr, request)

        @d.addCallback
        def _cb(result):
            request.write.assert_called_with('child')

        return d

    def test_deferredRendering(self):
        kr = SimpleKlein()
        kr.deferred = Deferred()

        request = requestMock("/deferred")

        d = _render(kr, request)

        def _cb(result):
            request.write.assert_called_with('ok')

        d.addCallback(_cb)
        kr.deferred.callback('ok')

        return d

    def test_elementRendering(self):
        kr = SimpleKlein()
        request = requestMock("/element/foo")

        d = _render(kr, request)

        def _cb(result):
            request.write.assert_called_with("<h1>foo</h1>")

        d.addCallback(_cb)

        return d
