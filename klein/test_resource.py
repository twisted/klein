from twisted.trial import unittest

from klein import Klein
from klein.resource import KleinResource

from twisted.internet.defer import succeed, Deferred
from twisted.web import server
from twisted.web.resource import Resource
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
    request.__klein_branch_segments__ = []

    def render(resource):
        return _render(resource, request)

    def finish():
        request.notifyFinish.return_value.callback(None)
        request.finished = True

    def processingFailed(failure):
        request.failed = failure
        request.notifyFinish.return_value.errback(failure)

    request.finish.side_effect = finish
    request.render.side_effect = render
    request.processingFailed.side_effect = processingFailed

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


class LeafResource(Resource):
    isLeaf = True

    def render(self, request):
        return "I am a leaf in the wind."


class ChildResource(Resource):
    isLeaf = True

    def __init__(self, name):
        self._name = name

    def render(self, request):
        return "I'm a child named %s!" % (self._name,)


class ChildrenResource(Resource):
    def render(self, request):
        return "I have children!"

    def getChild(self, path, request):
        return ChildResource(path)



class KleinResourceTests(unittest.TestCase):
    def setUp(self):
        self.app = Klein()
        self.kr = KleinResource(self.app)


    def test_simpleRouting(self):
        app = self.app

        @app.route("/")
        def slash(request):
            return 'ok'

        request = requestMock('/')

        d = _render(self.kr, request)

        def _cb(result):
            request.write.assert_called_with('ok')

        d.addCallback(_cb)

        return d


    def test_branchWithExplicitChildrenRouting(self):
        app = self.app

        @app.route("/")
        def slash(request):
            return 'ok'

        @app.route("/zeus")
        def wooo(request):
            return 'zeus'

        request = requestMock('/zeus')
        request2 = requestMock('/children')

        d = _render(self.kr, request)

        def _cb(result):
            request.write.assert_called_with('zeus')
            return _render(self.kr, request2)

        d.addCallback(_cb)

        def _cb2(result):
            request2.write.assert_called_with('ok')

        d.addCallback(_cb2)

        return d


    def test_deferredRendering(self):
        app = self.app

        deferredResponse = Deferred()

        @app.route("/deferred")
        def deferred(request):
            return deferredResponse

        request = requestMock("/deferred")

        d = _render(self.kr, request)

        def _cb(result):
            request.write.assert_called_with('ok')

        d.addCallback(_cb)
        deferredResponse.callback('ok')

        return d


    def test_elementRendering(self):
        app = self.app

        @app.route("/element/<string:name>")
        def element(request, name):
            return SimpleElement(name)

        request = requestMock("/element/foo")

        d = _render(self.kr, request)

        def _cb(result):
            request.write.assert_called_with("<h1>foo</h1>")

        d.addCallback(_cb)

        return d


    def test_leafResourceRendering(self):
        app = self.app

        request = requestMock("/resource/leaf")

        @app.route("/resource/leaf")
        def leaf(request):
            return LeafResource()

        d = _render(self.kr, request)
        def _cb(result):
            request.write.assert_called_with("I am a leaf in the wind.")

        d.addCallback(_cb)

        return d


    def test_childResourceRendering(self):
        app = self.app
        request = requestMock("/resource/children/betty")

        @app.route("/resource/children/")
        def children(request):
            return ChildrenResource()

        d = _render(self.kr, request)
        def _cb(result):
            request.write.assert_called_with("I'm a child named betty!")

        d.addCallback(_cb)

        return d

#    test_childResourceRendering.skip = "Resource rendering not supported."


    def test_childrenResourceRendering(self):
        app = self.app

        request = requestMock("/resource/children/")

        @app.route("/resource/children/")
        def children(request):
            return ChildrenResource()

        d = _render(self.kr, request)
        def _cb(result):
            request.write.assert_called_with("I have children!")

        d.addCallback(_cb)

        return d

#    test_childrenResourceRendering.skip = "Resource rendering not supported."


    def test_notFound(self):
        request = requestMock("/fourohofour")

        d = _render(self.kr, request)

        def _cb(result):
            request.setResponseCode.assert_called_with(404)
            self.assertIn("404 Not Found",
                request.write.mock_calls[0][1][0])

        d.addCallback(_cb)
        return d


    def test_renderUnicode(self):
        app = self.app

        request = requestMock("/snowman")

        @app.route("/snowman")
        def snowman(request):
            return u'\u2603'

        d = _render(self.kr, request)

        def _cb(result):
            request.write.assert_called_with("\xE2\x98\x83")

        d.addCallback(_cb)
        return d


    def test_renderNone(self):
        app = self.app

        request = requestMock("/None")

        @app.route("/None")
        def none(request):
            return None

        d = _render(self.kr, request)

        def _cb(result):
            self.assertEqual(request.write.called, False)
            request.finish.assert_called_with()

        d.addCallback(_cb)
        return d

