import os

from StringIO import StringIO

from twisted.trial import unittest

from klein import Klein

from klein.interfaces import IKleinRequest
from klein.resource import KleinResource, ensure_utf8_bytes

from twisted.internet.defer import succeed, Deferred, fail, CancelledError
from twisted.internet.error import ConnectionLost
from twisted.web import server
from twisted.web.static import File
from twisted.web.resource import Resource
from twisted.web.template import Element, XMLString, renderer
from twisted.web.test.test_web import DummyChannel
from twisted.web.http_headers import Headers

from werkzeug.exceptions import NotFound

from mock import Mock, call


def requestMock(path, method="GET", host="localhost", port=8080, isSecure=False,
                body=None, headers=None):
    if not headers:
        headers = {}

    if not body:
        body = ''

    request = server.Request(DummyChannel(), False)
    request.site = Mock(server.Site)
    request.gotLength(len(body))
    request.content = StringIO()
    request.content.write(body)
    request.content.seek(0)
    request.requestHeaders = Headers(headers)
    request.setHost(host, port, isSecure)
    request.uri = path
    request.prepath = []
    request.postpath = path.split('/')[1:]
    request.method = method
    request.clientproto = 'HTTP/1.1'

    request.setHeader = Mock(wraps=request.setHeader)
    request.setResponseCode = Mock(wraps=request.setResponseCode)

    request.finish = Mock(wraps=request.finish)
    request.write = Mock(wraps=request.write)

    def registerProducer(producer, streaming):
        # This is a terrible terrible hack.
        producer.resumeProducing()
        producer.resumeProducing()

    request.registerProducer = registerProducer
    request.unregisterProducer = Mock()

    request.processingFailed = Mock(wraps=request.processingFailed)

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

        @app.route("/", branch=True)
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

        @app.route("/", branch=True)
        def slash(request):
            return 'ok'

        @app.route("/zeus/", branch=True)
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

        @app.route("/resource/children/", branch=True)
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

        @app.route("/resource/children/", branch=True)
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

        @app.route("/", branch=True)
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

        @app.route("/static/", branch=True)
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

        @app.route("/", branch=True)
        def root(request):
            return File(os.path.dirname(__file__))

        d = _render(self.kr, request)

        def _cb(result):
            self.assertEqual(request.write.call_count, 1)
            [c] = request.write.mock_calls
            self.assertIn('Directory listing', c[1][0])
            request.finish.assert_called_once_with()

        d.addCallback(_cb)
        return d

    def test_addSlash(self):
        app = self.app
        request = requestMock("/foo")

        @app.route("/foo/")
        def foo(request):
            return "foo"

        d = _render(self.kr, request)

        def _cb(result):
            self.assertEqual(request.setHeader.call_count, 3)
            request.setHeader.assert_has_calls(
                [call('Content-Type', 'text/html; charset=utf-8'),
                 call('Content-Length', '259'),
                 call('Location', 'http://localhost:8080/foo/')])

        d.addCallback(_cb)
        return d

    def test_methodNotAllowed(self):
        app = self.app
        request = requestMock("/foo", method='DELETE')

        @app.route("/foo", methods=['GET'])
        def foo(request):
            return "foo"

        d = _render(self.kr, request)

        def _cb(result):
            self.assertEqual(request.code, 405)

        d.addCallback(_cb)
        return d

    def test_methodNotAllowedWithRootCollection(self):
        app = self.app
        request = requestMock("/foo/bar", method='DELETE')

        @app.route("/foo/bar", methods=['GET'])
        def foobar(request):
            return "foo/bar"

        @app.route("/foo/", methods=['DELETE'])
        def foo(request):
            return "foo"

        d = _render(self.kr, request)

        def _cb(result):
            self.assertEqual(request.code, 405)

        d.addCallback(_cb)
        return d

    def test_noImplicitBranch(self):
        app = self.app
        request = requestMock("/foo")

        @app.route("/")
        def root(request):
            return "foo"

        d = _render(self.kr, request)

        def _cb(result):
            self.assertEqual(request.code, 404)

        d.addCallback(_cb)
        return d

    def test_strictSlashes(self):
        app = self.app
        request = requestMock("/foo/bar")

        request_url = [None]

        @app.route("/foo/bar/", strict_slashes=False)
        def root(request):
            request_url[0] = request.URLPath()
            return "foo"

        d = _render(self.kr, request)

        def _cb(result):
            self.assertEqual(str(request_url[0]), "http://localhost:8080/foo/bar")
            request.write.assert_called_with('foo')
            self.assertEqual(request.code, 200)

        d.addCallback(_cb)
        return d

    def test_URLPath(self):
        app = self.app
        request = requestMock('/egg/chicken')

        request_url = [None]

        @app.route("/egg/chicken")
        def wooo(request):
            request_url[0] = request.URLPath()
            return 'foo'

        d = _render(self.kr, request)

        def _cb(result):
            self.assertEqual(str(request_url[0]), 'http://localhost:8080/egg/chicken')

        d.addCallback(_cb)
        return d

    def test_URLPath_root(self):
        app = self.app
        request = requestMock('/')

        request_url = [None]

        @app.route("/")
        def root(request):
            request_url[0] = request.URLPath()

        d = _render(self.kr, request)

        def _cb(result):
            self.assertEqual(str(request_url[0]), 'http://localhost:8080/')

        d.addCallback(_cb)
        return d

    def test_URLPath_traversedResource(self):
        app = self.app
        request = requestMock('/resource/foo')

        request_url = [None]

        class URLPathResource(Resource):
            def render(self, request):
                request_url[0] = request.URLPath()

            def getChild(self, request, segment):
                return self

        @app.route("/resource/", branch=True)
        def root(request):
            return URLPathResource()

        d = _render(self.kr, request)

        def _cb(result):
            self.assertEqual(str(request_url[0]), 'http://localhost:8080/resource/foo')

        d.addCallback(_cb)
        return d

    def test_handlerRaises(self):
        app = self.app
        request = requestMock("/")

        failures = []

        class RouteFailureTest(Exception):
            pass

        @app.route("/")
        def root(request):
            def _capture_failure(f):
                failures.append(f)
                return f

            return fail(RouteFailureTest("die")).addErrback(_capture_failure)

        d = _render(self.kr, request)

        def _cb(result):
            self.assertEqual(request.code, 500)
            request.processingFailed.assert_called_once_with(failures[0])
            self.flushLoggedErrors(RouteFailureTest)

        d.addCallback(_cb)
        return d

    def test_genericErrorHandler(self):
        app = self.app
        request = requestMock("/")

        failures = []

        class RouteFailureTest(Exception):
            pass

        @app.route("/")
        def root(request):
            raise RouteFailureTest("not implemented")

        @app.handle_errors
        def handle_errors(request, failure):
            failures.append(failure)
            request.setResponseCode(501)
            return

        d = _render(self.kr, request)

        def _cb(result):
            self.assertEqual(request.code, 501)
            assert not request.processingFailed.called

        d.addCallback(_cb)
        return d

    def test_typeSpecificErrorHandlers(self):
        app = self.app
        request = requestMock("/")
        type_error_handled = False
        generic_error_handled = False

        failures = []

        class TypeFilterTestError(Exception):
            pass

        @app.route("/")
        def root(request):
            return fail(TypeFilterTestError("not implemented"))

        @app.handle_errors(TypeError)
        def handle_type_error(request, failure):
            type_error_handled = True
            return

        @app.handle_errors(TypeFilterTestError)
        def handle_type_filter_test_error(request, failure):
            failures.append(failure)
            request.setResponseCode(501)
            return

        @app.handle_errors
        def handle_generic_error(request, failure):
            generic_error_handled = True
            return

        d = _render(self.kr, request)

        def _cb(result):
            self.assertEqual(request.processingFailed.called, False)
            self.assertEqual(type_error_handled, False)
            self.assertEqual(generic_error_handled, False)
            self.assertEqual(len(failures), 1)
            self.assertEqual(request.code, 501)

        d.addCallback(_cb)
        return d

    def test_notFoundException(self):
        app = self.app
        request = requestMock("/foo")
        generic_error_handled = False

        @app.route("/")
        def root(request):
            pass

        @app.handle_errors(NotFound)
        def handle_not_found(request, failure):
            request.setResponseCode(404)
            return 'Custom Not Found'

        @app.handle_errors
        def handle_generic_error(request, failure):
            generic_error_handled = True
            return

        d = _render(self.kr, request)

        def _cb(result):
            self.assertEqual(request.processingFailed.called, False)
            self.assertEqual(generic_error_handled, False)
            self.assertEqual(request.code, 404)
            request.write.assert_called_once_with('Custom Not Found')

        d.addCallback(_cb)
        return d

    def test_requestWriteAfterFinish(self):
        app = self.app
        request = requestMock("/")

        @app.route("/")
        def root(request):
            request.finish()
            return 'foo'

        d = _render(self.kr, request)

        def _cb(result):
            self.assertEqual(request.write.mock_calls, [call(''), call('foo')])
            [failure] = self.flushLoggedErrors(RuntimeError)

            self.assertEqual(
                str(failure.value),
                ("Request.write called on a request after Request.finish was "
                 "called."))

        d.addCallback(_cb)
        return d

    def test_requestFinishAfterConnectionLost(self):
        app = self.app
        request = requestMock("/")

        finished = Deferred()

        @app.route("/")
        def root(request):
            request.notifyFinish().addBoth(lambda _: finished.callback('foo'))
            return finished

        d = _render(self.kr, request)

        def _eb(result):
            [failure] = self.flushLoggedErrors(RuntimeError)

            self.assertEqual(
                str(failure.value),
                ("Request.finish called on a request after its connection was "
                 "lost; use Request.notifyFinish to keep track of this."))

        d.addErrback(lambda _: finished)
        d.addErrback(_eb)

        request.connectionLost(ConnectionLost())

        return d

    def test_routeHandlesRequestFinished(self):
        app = self.app
        request = requestMock("/")

        cancelled = []

        @app.route("/")
        def root(request):
            _d = Deferred()
            _d.addErrback(cancelled.append)
            request.notifyFinish().addCallback(lambda _: _d.cancel())
            return _d

        d = _render(self.kr, request)

        request.finish()

        def _cb(result):
            cancelled[0].trap(CancelledError)
            request.write.assert_called_once_with('')
            self.assertEqual(request.processingFailed.call_count, 0)

        d.addCallback(_cb)
        return d

    def test_url_for(self):
        app = self.app
        request = requestMock('/foo/1')

        relative_url = [None]

        @app.route("/foo/<int:bar>")
        def foo(request, bar):
            krequest = IKleinRequest(request)
            relative_url[0] = krequest.url_for('foo', {'bar': bar + 1})

        d = _render(self.kr, request)

        def _cb(result):
            self.assertEqual(relative_url[0], '/foo/2')

        d.addCallback(_cb)
        return d

    def test_cancelledDeferred(self):
        app = self.app
        request = requestMock("/")

        inner_d = Deferred()

        @app.route("/")
        def root(request):
            return inner_d

        d = _render(self.kr, request)

        inner_d.cancel()

        def _cb(result):
            self.assertIdentical(result, None)
            self.flushLoggedErrors(CancelledError)

        d.addCallback(_cb)
        return d

    def test_external_url_for(self):
        app = self.app
        request = requestMock('/foo/1')

        relative_url = [None]

        @app.route("/foo/<int:bar>")
        def foo(request, bar):
            krequest = IKleinRequest(request)
            relative_url[0] = krequest.url_for('foo', {'bar': bar + 1}, force_external=True)

        d = _render(self.kr, request)

        def _cb(result):
            self.assertEqual(relative_url[0], 'http://localhost:8080/foo/2')

        d.addCallback(_cb)
        return d

    def test_cancelledIsEatenOnConnectionLost(self):
        app = self.app
        request = requestMock("/")

        @app.route("/")
        def root(request):
            _d = Deferred()
            request.notifyFinish().addErrback(lambda _: _d.cancel())
            return _d

        d = _render(self.kr, request)

        request.connectionLost(ConnectionLost())

        def _cb(result):
            self.assertEqual(request.processingFailed.call_count, 0)

        d.addErrback(lambda f: f.trap(ConnectionLost))
        d.addCallback(_cb)
        return d

    def test_cancelsOnConnectionLost(self):
        app = self.app
        request = requestMock("/")

        handler_d = Deferred()

        @app.route("/")
        def root(request):
            return handler_d

        d = _render(self.kr, request)
        request.connectionLost(ConnectionLost())

        handler_d.addErrback(lambda f: f.trap(CancelledError))

        d.addErrback(lambda f: f.trap(ConnectionLost))
        d.addCallback(lambda _: handler_d)

        return d

    def test_ensure_utf8_bytes(self):
        self.assertEqual(ensure_utf8_bytes(u"abc"), "abc")
        self.assertEqual(ensure_utf8_bytes(u"\u2202"), "\xe2\x88\x82")
        self.assertEqual(ensure_utf8_bytes("\xe2\x88\x82"), "\xe2\x88\x82")
