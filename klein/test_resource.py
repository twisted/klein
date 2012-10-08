import os

from StringIO import StringIO

from twisted.trial import unittest

from klein import Klein
from klein.resource import KleinResource

from twisted.internet.defer import succeed, Deferred
from twisted.web import server
from twisted.web.static import File
from twisted.web.resource import Resource
from twisted.web.template import Element, XMLString, renderer
from twisted.web.test.test_web import DummyChannel
from twisted.web.http_headers import Headers
from mock import Mock


def requestMock(path, method="GET", host="localhost", port=8080, isSecure=False,
                body=None, headers=None):
    if not headers:
        headers = {}

    if not body:
        body = ''

    request = server.Request(DummyChannel(), False)
    request.gotLength(len(body))
    request.content = StringIO()
    request.content.write(body)
    request.requestHeaders = Headers(headers)
    request.setHost(host, port, isSecure)
    request.uri = path
    request.prepath = []
    request.postpath = path.split('/')
    request.method = method
    request.clientproto = 'HTTP/1.1'

    request.setResponseCode = Mock(wraps=request.setResponseCode)
    request.finish = Mock(wraps=request.finish)
    request.write = Mock(wraps=request.write)

    def registerProducer(producer, streaming):
        # This is a terrible terrible hack.
        producer.resumeProducing()
        producer.resumeProducing()

    request.registerProducer = registerProducer
    request.unregisterProducer = Mock()

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
        if path == '':
            return self

        return ChildResource(path)



class KleinResourceTests(unittest.TestCase):
    def setUp(self):
        self.app = Klein()
        self.kr = KleinResource(self.app)


    def test_simplePost(self):
        app = self.app

        # The order in which these functions are defined
        # matters.  If the more generic one is defined first
        # then it will eat requests that should have been handled
        # by the more specific handler.

        @app.route("/", methods=["POST"])
        def handle_post(request):
            return 'posted'

        @app.route("/")
        def handle(request):
            return 'gotted'

        request = requestMock('/', 'POST')
        request2 = requestMock('/')


        d = _render(self.kr, request)

        def _cb(result):
            request.write.assert_called_with('posted')
            return _render(self.kr, request2)

        d.addCallback(_cb)

        def _cb2(result):
            request2.write.assert_called_with('gotted')

        d.addCallback(_cb2)
        return d


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


    def test_branchRendering(self):
        app = self.app

        @app.route("/")
        def slash(request):
            return 'ok'

        request = requestMock('/foo')

        d = _render(self.kr, request)

        def _cb(result):
            request.write.assert_called_once_with('ok')

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
        request2 = requestMock('/')

        d = _render(self.kr, request)

        def _cb(result):
            request.write.assert_called_with('zeus')
            return _render(self.kr, request2)

        d.addCallback(_cb)

        def _cb2(result):
            request2.write.assert_called_with('ok')

        d.addCallback(_cb2)

        return d


    def test_branchWithExplicitChildBranch(self):
        app = self.app

        @app.route("/")
        def slash(request):
            return 'ok'

        @app.route("/zeus/")
        def wooo(request):
            return 'zeus'

        request = requestMock('/zeus/foo')
        request2 = requestMock('/')

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
            request.write.assert_called_once_with('')
            request.finish.assert_called_once_with()

        d.addCallback(_cb)
        return d


    def test_staticRoot(self):
        app = self.app
        request = requestMock("/__init__.py")

        @app.route("/")
        def root(request):
            return File(os.path.dirname(__file__))

        d = _render(self.kr, request)

        def _cb(result):
            request.write.assert_called_once_with(
                open(
                    os.path.join(
                        os.path.dirname(__file__), "__init__.py")).read())
            request.finish.assert_called_once_with()

        d.addCallback(_cb)
        return d


    def test_explicitStaticBranch(self):
        app = self.app

        request = requestMock("/static/__init__.py")

        @app.route("/static/")
        def root(request):
            return File(os.path.dirname(__file__))

        d = _render(self.kr, request)

        def _cb(result):
            request.write.assert_called_once_with(
                open(
                    os.path.join(
                        os.path.dirname(__file__), "__init__.py")).read())
            request.finish.assert_called_once_with()

        d.addCallback(_cb)
        return d

    def test_staticDirlist(self):
        app = self.app

        request = requestMock("/")

        @app.route("/")
        def root(request):
            return File(os.path.dirname(__file__))

        d = _render(self.kr, request)

        def _cb(result):
            self.assertEqual(request.write.call_count, 1)
            [call] = request.write.mock_calls
            self.assertIn('Directory listing', call[1][0])
            request.finish.assert_called_once_with()

        d.addCallback(_cb)
        return d
