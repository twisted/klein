from __future__ import absolute_import, division

import os
from io import BytesIO

from mock import Mock, call

from six.moves.urllib.parse import parse_qs

from twisted.internet.defer import CancelledError, Deferred, fail, succeed
from twisted.internet.error import ConnectionLost
from twisted.internet.unix import Server
from twisted.python.compat import _PY3, unicode
from twisted.web import server
from twisted.web.http_headers import Headers
from twisted.web.resource import Resource
from twisted.web.static import File
from twisted.web.template import Element, XMLString, renderer
from twisted.web.test.test_web import DummyChannel

from werkzeug.exceptions import NotFound

from klein import Klein
from klein.interfaces import IKleinRequest
from klein.resource import (
    KleinResource, _URLDecodeError, _extractURLparts, ensure_utf8_bytes
)
from klein.test.util import EqualityTestsMixin, TestCase


def requestMock(path, method=b"GET", host=b"localhost", port=8080,
                isSecure=False, body=None, headers=None):
    if not headers:
        headers = {}

    if not body:
        body = b''

    path, qpath = (path.split(b"?", 1) + [b""])[:2]

    request = server.Request(DummyChannel(), False)
    request.site = Mock(server.Site)
    request.gotLength(len(body))
    request.content = BytesIO()
    request.content.write(body)
    request.content.seek(0)
    request.args = parse_qs(qpath)
    request.requestHeaders = Headers(headers)
    request.setHost(host, port, isSecure)
    request.uri = path
    request.prepath = []
    request.postpath = path.split(b'/')[1:]
    request.method = method
    request.clientproto = b'HTTP/1.1'

    request.setHeader = Mock(wraps=request.setHeader)
    request.setResponseCode = Mock(wraps=request.setResponseCode)

    request._written = BytesIO()
    request.finishCount = 0
    request.writeCount = 0

    def registerProducer(producer, streaming):
        request.producer = producer
        for _ in range(2):
            if request.producer:
                request.producer.resumeProducing()

    def unregisterProducer():
        request.producer = None

    def finish():
        request.finishCount += 1

        if not request.startedWriting:
            request.write(b'')

        if not request.finished:
            request.finished = True
            request._cleanup()

    def write(data):
        request.writeCount += 1
        request.startedWriting = True

        if not request.finished:
            request._written.write(data)
        else:
            raise RuntimeError('Request.write called on a request after '
                               'Request.finish was called.')

    def getWrittenData():
        return request._written.getvalue()

    request.finish = finish
    request.write = write
    request.getWrittenData = getWrittenData

    request.registerProducer = registerProducer
    request.unregisterProducer = unregisterProducer

    request.processingFailed = Mock(wraps=request.processingFailed)

    return request


def _render(resource, request, notifyFinish=True):
    result = resource.render(request)

    if isinstance(result, bytes):
        request.write(result)
        request.finish()
        return succeed(None)
    elif result is server.NOT_DONE_YET:
        if request.finished or not notifyFinish:
            return succeed(None)
        else:
            return request.notifyFinish()
    else:
        raise ValueError("Unexpected return value: {!r}".format(result))


class SimpleElement(Element):
    loader = XMLString(
        '<h1 xmlns:t="http://twistedmatrix.com/ns/twisted.web.template/0.1" '
        't:render="name" />'
    )

    def __init__(self, name):
        self._name = name

    @renderer
    def name(self, request, tag):
        return tag(self._name)

class DeferredElement(SimpleElement):
    @renderer
    def name(self, request, tag):
        self.deferred = Deferred()
        self.deferred.addCallback(lambda ignored: tag(self._name))
        return self.deferred

class LeafResource(Resource):
    isLeaf = True

    def render(self, request):
        return b"I am a leaf in the wind."


class ChildResource(Resource):
    isLeaf = True

    def __init__(self, name):
        self._name = name

    def render(self, request):
        return b"I'm a child named " + self._name + b"!"


class ChildrenResource(Resource):
    def render(self, request):
        return b"I have children!"

    def getChild(self, path, request):
        if path == b'':
            return self

        return ChildResource(path)


class ProducingResource(Resource):
    def __init__(self, path, strings):
        self.path = path
        self.strings = strings

    def render_GET(self, request):
        producer = MockProducer(request, self.strings)
        producer.start()
        return server.NOT_DONE_YET


class MockProducer(object):
    def __init__(self, request, strings):
        self.request = request
        self.strings = strings

    def start(self):
        self.request.registerProducer(self, False)

    def resumeProducing(self):
        if self.strings:
            self.request.write(self.strings.pop(0))
        else:
            self.request.unregisterProducer()
            self.request.finish()



class KleinResourceEqualityTests(TestCase, EqualityTestsMixin):
    """
    Tests for L{KleinResource}'s implementation of C{==} and C{!=}.
    """
    class _One(object):
        oneKlein = Klein()

        @oneKlein.route("/foo")
        def foo(self):
            pass

    _one = _One()


    class _Another(object):
        anotherKlein = Klein()

        @anotherKlein.route("/bar")
        def bar(self):
            pass

    _another = _Another()


    def anInstance(self):
        return self._one.oneKlein


    def anotherInstance(self):
        return self._another.anotherKlein



class KleinResourceTests(TestCase):
    def setUp(self):
        self.app = Klein()
        self.kr = KleinResource(self.app)


    def assertFired(self, deferred, result=None):
        """
        Assert that the given deferred has fired with the given result.
        """
        self.assertEqual(self.successResultOf(deferred), result)


    def assertNotFired(self, deferred):
        """
        Assert that the given deferred has not fired with a result.
        """
        _pawn = object()
        result = getattr(deferred, 'result', _pawn)
        if result != _pawn:
            self.fail(
                "Expected deferred not to have fired, but it has: {!r}"
                .format(deferred)
            )


    def test_simplePost(self):
        app = self.app

        # The order in which these functions are defined
        # matters.  If the more generic one is defined first
        # then it will eat requests that should have been handled
        # by the more specific handler.

        @app.route("/", methods=["POST"])
        def handle_post(request):
            return b'posted'

        @app.route("/")
        def handle(request):
            return b'gotted'

        request = requestMock(b'/', b'POST')
        request2 = requestMock(b'/')

        d = _render(self.kr, request)
        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), b'posted')

        d2 = _render(self.kr, request2)
        self.assertFired(d2)
        self.assertEqual(request2.getWrittenData(), b'gotted')


    def test_simpleRouting(self):
        app = self.app

        @app.route("/")
        def slash(request):
            return b'ok'

        request = requestMock(b'/')

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), b'ok')


    def test_branchRendering(self):
        app = self.app

        @app.route("/", branch=True)
        def slash(request):
            return b'ok'

        request = requestMock(b'/foo')

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), b'ok')


    def test_branchWithExplicitChildrenRouting(self):
        app = self.app

        @app.route("/")
        def slash(request):
            return b'ok'

        @app.route("/zeus")
        def wooo(request):
            return b'zeus'

        request = requestMock(b'/zeus')
        request2 = requestMock(b'/')

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), b'zeus')

        d2 = _render(self.kr, request2)

        self.assertFired(d2)
        self.assertEqual(request2.getWrittenData(), b'ok')


    def test_branchWithExplicitChildBranch(self):
        app = self.app

        @app.route("/", branch=True)
        def slash(request):
            return b'ok'

        @app.route("/zeus/", branch=True)
        def wooo(request):
            return b'zeus'

        request = requestMock(b'/zeus/foo')
        request2 = requestMock(b'/')

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), b'zeus')

        d2 = _render(self.kr, request2)

        self.assertFired(d2)
        self.assertEqual(request2.getWrittenData(), b'ok')


    def test_deferredRendering(self):
        app = self.app

        deferredResponse = Deferred()

        @app.route("/deferred")
        def deferred(request):
            return deferredResponse

        request = requestMock(b"/deferred")

        d = _render(self.kr, request)

        self.assertNotFired(d)

        deferredResponse.callback(b'ok')

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), b'ok')


    def test_elementRendering(self):
        app = self.app

        @app.route("/element/<string:name>")
        def element(request, name):
            return SimpleElement(name)

        request = requestMock(b"/element/foo")

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(),
                         b"<!DOCTYPE html>\n<h1>foo</h1>")


    def test_deferredElementRendering(self):
        app = self.app

        elements = []

        @app.route("/element/<string:name>")
        def element(request, name):
            it = DeferredElement(name)
            elements.append(it)
            return it

        request = requestMock(b"/element/bar")

        d = _render(self.kr, request)
        self.assertEqual(len(elements), 1)
        [oneElement] = elements
        self.assertNoResult(d)
        oneElement.deferred.callback(None)
        self.assertFired(d)
        self.assertEqual(request.getWrittenData(),
                         b"<!DOCTYPE html>\n<h1>bar</h1>")


    def test_leafResourceRendering(self):
        app = self.app

        request = requestMock(b"/resource/leaf")

        @app.route("/resource/leaf")
        def leaf(request):
            return LeafResource()

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), b"I am a leaf in the wind.")


    def test_childResourceRendering(self):
        app = self.app
        request = requestMock(b"/resource/children/betty")

        @app.route("/resource/children/", branch=True)
        def children(request):
            return ChildrenResource()

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(
            request.getWrittenData(), b"I'm a child named betty!"
        )


    def test_childrenResourceRendering(self):
        app = self.app

        request = requestMock(b"/resource/children/")

        @app.route("/resource/children/", branch=True)
        def children(request):
            return ChildrenResource()

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), b"I have children!")


    def test_producerResourceRendering(self):
        """
        Test that Klein will correctly handle producing L{Resource}s.

        Producing Resources close the connection by themselves, sometimes after
        Klein has 'finished'. This test lets Klein finish its handling of the
        request before doing more producing.
        """
        app = self.app

        request = requestMock(b"/resource")

        @app.route("/resource", branch=True)
        def producer(request):
            return ProducingResource(request, [b"a", b"b", b"c", b"d"])

        d = _render(self.kr, request, notifyFinish=False)

        self.assertNotEqual(
            request.getWrittenData(), b"abcd",
            "The full response should not have been written at this point."
        )

        while request.producer:
            request.producer.resumeProducing()

        self.assertEqual(self.successResultOf(d), None)
        self.assertEqual(request.getWrittenData(), b"abcd")
        self.assertEqual(request.writeCount, 4)
        self.assertEqual(request.finishCount, 1)
        self.assertEqual(request.producer, None)


    def test_notFound(self):
        request = requestMock(b"/fourohofour")

        d = _render(self.kr, request)

        self.assertFired(d)
        request.setResponseCode.assert_called_with(404)
        self.assertIn(b"404 Not Found", request.getWrittenData())


    def test_renderUnicode(self):
        app = self.app

        request = requestMock(b"/snowman")

        @app.route("/snowman")
        def snowman(request):
            return u'\u2603'

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), b"\xE2\x98\x83")


    def test_renderNone(self):
        app = self.app

        request = requestMock(b"/None")

        @app.route("/None")
        def none(request):
            return None

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), b'')
        self.assertEqual(request.finishCount, 1)
        self.assertEqual(request.writeCount, 1)


    def test_staticRoot(self):
        app = self.app

        request = requestMock(b"/__init__.py")
        expected = open(
            os.path.join(os.path.dirname(__file__), "__init__.py"), 'rb'
        ).read()

        @app.route("/", branch=True)
        def root(request):
            return File(os.path.dirname(__file__))

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), expected)
        self.assertEqual(request.finishCount, 1)


    def test_explicitStaticBranch(self):
        app = self.app

        request = requestMock(b"/static/__init__.py")
        expected = open(
            os.path.join(os.path.dirname(__file__), "__init__.py"), 'rb'
        ).read()

        @app.route("/static/", branch=True)
        def root(request):
            return File(os.path.dirname(__file__))

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), expected)
        self.assertEqual(request.writeCount, 1)
        self.assertEqual(request.finishCount, 1)

    def test_staticDirlist(self):
        app = self.app

        request = requestMock(b"/")

        @app.route("/", branch=True)
        def root(request):
            return File(os.path.dirname(__file__))

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertIn(b'Directory listing', request.getWrittenData())
        self.assertEqual(request.writeCount, 1)
        self.assertEqual(request.finishCount, 1)

    def test_addSlash(self):
        app = self.app
        request = requestMock(b"/foo")

        @app.route("/foo/")
        def foo(request):
            return "foo"

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.setHeader.call_count, 3)
        request.setHeader.assert_has_calls([
            call(b'Content-Type', b'text/html; charset=utf-8'),
            call(b'Content-Length', b'259'),
            call(b'Location', b'http://localhost:8080/foo/')
        ])

    def test_methodNotAllowed(self):
        app = self.app
        request = requestMock(b"/foo", method=b'DELETE')

        @app.route("/foo", methods=['GET'])
        def foo(request):
            return "foo"

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.code, 405)

    def test_methodNotAllowedWithRootCollection(self):
        app = self.app
        request = requestMock(b"/foo/bar", method=b'DELETE')

        @app.route("/foo/bar", methods=['GET'])
        def foobar(request):
            return b"foo/bar"

        @app.route("/foo/", methods=['DELETE'])
        def foo(request):
            return b"foo"

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.code, 405)

    def test_noImplicitBranch(self):
        app = self.app
        request = requestMock(b"/foo")

        @app.route("/")
        def root(request):
            return b"foo"

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.code, 404)

    def test_strictSlashes(self):
        app = self.app
        request = requestMock(b"/foo/bar")

        request_url = [None]

        @app.route("/foo/bar/", strict_slashes=False)
        def root(request):
            request_url[0] = request.URLPath()
            return b"foo"

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(str(request_url[0]), "http://localhost:8080/foo/bar")
        self.assertEqual(request.getWrittenData(), b'foo')
        self.assertEqual(request.code, 200)

    def test_URLPath(self):
        app = self.app
        request = requestMock(b'/egg/chicken')

        request_url = [None]

        @app.route("/egg/chicken")
        def wooo(request):
            request_url[0] = request.URLPath()
            return b'foo'

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(
            str(request_url[0]), 'http://localhost:8080/egg/chicken'
        )

    def test_URLPath_root(self):
        app = self.app
        request = requestMock(b'/')

        request_url = [None]

        @app.route("/")
        def root(request):
            request_url[0] = request.URLPath()

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(str(request_url[0]), 'http://localhost:8080/')

    def test_URLPath_traversedResource(self):
        app = self.app
        request = requestMock(b'/resource/foo')

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

        self.assertFired(d)
        self.assertEqual(
            str(request_url[0]), 'http://localhost:8080/resource/foo'
        )

    def test_handlerRaises(self):
        app = self.app
        request = requestMock(b"/")

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

        self.assertFired(d)
        self.assertEqual(request.code, 500)
        request.processingFailed.assert_called_once_with(failures[0])
        self.flushLoggedErrors(RouteFailureTest)

    def test_genericErrorHandler(self):
        app = self.app
        request = requestMock(b"/")

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

        self.assertFired(d)
        self.assertEqual(request.code, 501)
        assert not request.processingFailed.called

    def test_typeSpecificErrorHandlers(self):
        app = self.app
        request = requestMock(b"/")
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
            global type_error_handled
            type_error_handled = True
            return

        @app.handle_errors(TypeFilterTestError)
        def handle_type_filter_test_error(request, failure):
            failures.append(failure)
            request.setResponseCode(501)
            return

        @app.handle_errors
        def handle_generic_error(request, failure):
            global generic_error_handled
            generic_error_handled = True
            return

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.processingFailed.called, False)
        self.assertEqual(type_error_handled, False)
        self.assertEqual(generic_error_handled, False)
        self.assertEqual(len(failures), 1)
        self.assertEqual(request.code, 501)

    def test_notFoundException(self):
        app = self.app
        request = requestMock(b"/")
        generic_error_handled = False

        @app.handle_errors(NotFound)
        def handle_not_found(request, failure):
            request.setResponseCode(404)
            return b'Custom Not Found'

        @app.handle_errors
        def handle_generic_error(request, failure):
            global generic_error_handled
            generic_error_handled = True
            return

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.processingFailed.called, False)
        self.assertEqual(generic_error_handled, False)
        self.assertEqual(request.code, 404)
        self.assertEqual(request.getWrittenData(), b'Custom Not Found')
        self.assertEqual(request.writeCount, 1)

    def test_errorHandlerNeedsRendering(self):
        """
        Renderables returned by L{handle_errors} are rendered.
        """
        app = self.app
        request = requestMock(b"/")

        @app.handle_errors(NotFound)
        def handle_not_found(request, failure):
            return SimpleElement("Not Found Element")

        d = _render(self.kr, request)

        rendered = b"<!DOCTYPE html>\n<h1>Not Found Element</h1>"

        self.assertFired(d)
        self.assertEqual(request.processingFailed.called, False)
        self.assertEqual(request.getWrittenData(), rendered)

    def test_errorHandlerReturnsResource(self):
        """
        Resources returned by L{Klein.handle_errors} are rendered
        """
        app = self.app
        request = requestMock(b"/")

        class NotFoundResource(Resource):
            isLeaf = True

            def render(self, request):
                request.setResponseCode(404)
                return b'Nothing found'

        @app.handle_errors(NotFound)
        def handle_not_found(request, failure):
            return NotFoundResource()

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.code, 404)
        self.assertEqual(request.getWrittenData(), b'Nothing found')

    def test_requestWriteAfterFinish(self):
        app = self.app
        request = requestMock(b"/")

        @app.route("/")
        def root(request):
            request.finish()
            return b'foo'

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.writeCount, 2)
        self.assertEqual(request.getWrittenData(), b'')
        [failure] = self.flushLoggedErrors(RuntimeError)

        self.assertEqual(
            str(failure.value),
            ("Request.write called on a request after Request.finish was "
             "called."))

    def test_requestFinishAfterConnectionLost(self):
        app = self.app
        request = requestMock(b"/")

        finished = Deferred()

        @app.route("/")
        def root(request):
            request.notifyFinish().addBoth(lambda _: finished.callback(b'foo'))
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

        self.assertNotFired(d)

        request.connectionLost(ConnectionLost())

        self.assertFired(d)


    def test_routeHandlesRequestFinished(self):
        app = self.app
        request = requestMock(b"/")

        cancelled = []

        @app.route("/")
        def root(request):
            _d = Deferred()
            _d.addErrback(cancelled.append)
            request.notifyFinish().addCallback(lambda _: _d.cancel())
            return _d

        d = _render(self.kr, request)

        request.finish()

        self.assertFired(d)

        cancelled[0].trap(CancelledError)
        self.assertEqual(request.getWrittenData(), b'')
        self.assertEqual(request.writeCount, 1)
        self.assertEqual(request.processingFailed.call_count, 0)

    def test_url_for(self):
        app = self.app
        request = requestMock(b'/foo/1')

        relative_url = [None]

        @app.route("/foo/<int:bar>")
        def foo(request, bar):
            krequest = IKleinRequest(request)
            relative_url[0] = krequest.url_for('foo', {'bar': bar + 1})

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(relative_url[0], '/foo/2')

    def test_cancelledDeferred(self):
        app = self.app
        request = requestMock(b"/")

        inner_d = Deferred()

        @app.route("/")
        def root(request):
            return inner_d

        d = _render(self.kr, request)

        inner_d.cancel()

        self.assertFired(d)
        self.flushLoggedErrors(CancelledError)

    def test_external_url_for(self):
        app = self.app
        request = requestMock(b'/foo/1')

        relative_url = [None]

        @app.route("/foo/<int:bar>")
        def foo(request, bar):
            krequest = IKleinRequest(request)
            relative_url[0] = krequest.url_for(
                'foo', {'bar': bar + 1}, force_external=True
            )

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(relative_url[0], 'http://localhost:8080/foo/2')

    def test_cancelledIsEatenOnConnectionLost(self):
        app = self.app
        request = requestMock(b"/")

        @app.route("/")
        def root(request):
            _d = Deferred()
            request.notifyFinish().addErrback(lambda _: _d.cancel())
            return _d

        d = _render(self.kr, request)

        self.assertNotFired(d)

        request.connectionLost(ConnectionLost())

        def _cb(result):
            self.assertEqual(request.processingFailed.call_count, 0)

        d.addErrback(lambda f: f.trap(ConnectionLost))
        d.addCallback(_cb)
        self.assertFired(d)

    def test_cancelsOnConnectionLost(self):
        app = self.app
        request = requestMock(b"/")

        handler_d = Deferred()

        @app.route("/")
        def root(request):
            return handler_d

        d = _render(self.kr, request)

        self.assertNotFired(d)

        request.connectionLost(ConnectionLost())

        handler_d.addErrback(lambda f: f.trap(CancelledError))

        d.addErrback(lambda f: f.trap(ConnectionLost))
        d.addCallback(lambda _: handler_d)
        self.assertFired(d)

    def test_ensure_utf8_bytes(self):
        self.assertEqual(ensure_utf8_bytes(u"abc"), b"abc")
        self.assertEqual(ensure_utf8_bytes(u"\u2202"), b"\xe2\x88\x82")
        self.assertEqual(ensure_utf8_bytes(b"\xe2\x88\x82"), b"\xe2\x88\x82")

    def test_decodesPath(self):
        """
        server_name, path_info, and script_name are decoded as UTF-8 before
        being handed to werkzeug.
        """
        request = requestMock(b"/f\xc3\xb6\xc3\xb6")

        _render(self.kr, request)
        kreq = IKleinRequest(request)
        self.assertIsInstance(kreq.mapper.server_name, unicode)
        self.assertIsInstance(kreq.mapper.path_info, unicode)
        self.assertIsInstance(kreq.mapper.script_name, unicode)

    def test_failedDecodePathInfo(self):
        """
        If decoding of one of the URL parts (in this case PATH_INFO) fails, the
        error is logged and 400 returned.
        """
        request = requestMock(b"/f\xc3\xc3\xb6")
        _render(self.kr, request)
        rv = request.getWrittenData()
        self.assertEqual(b"Non-UTF-8 encoding in URL.", rv)
        self.assertEqual(1, len(self.flushLoggedErrors(UnicodeDecodeError)))

    def test_urlDecodeErrorReprPy2(self):
        """
        URLDecodeError.__repr__ formats properly.
        """
        self.assertEqual(
            "<URLDecodeError(errors=<type 'exceptions.ValueError'>)>",
            repr(_URLDecodeError(ValueError)),
        )

    def test_urlDecodeErrorReprPy3(self):
        """
        URLDecodeError.__repr__ formats properly.
        """
        self.assertEqual(
            "<URLDecodeError(errors=<class 'ValueError'>)>",
            repr(_URLDecodeError(ValueError)),
        )

    if _PY3:
        test_urlDecodeErrorReprPy2.skip = "Only works on Py2"
    else:
        test_urlDecodeErrorReprPy3.skip = "Only works on Py3"


    def test_subroutedBranch(self):
        subapp = Klein()

        @subapp.route('/foo')
        def foo(request):
            return b'foo'

        app = self.app
        with app.subroute('/sub') as app:
            @app.route('/app', branch=True)
            def subapp_endpoint(request):
                return subapp.resource()

        request = requestMock(b'/sub/app/foo')
        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), b'foo')


    def test_correctContentLengthForRequestRedirect(self):
        app = self.app

        @app.route('/alias', alias=True)
        @app.route('/real')
        def real(req):
            return b'42'

        request = requestMock(b'/real')
        d = _render(self.kr, request)
        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), b'42')

        request = requestMock(b'/alias')
        d = _render(self.kr, request)
        self.assertFired(d)
        request.setResponseCode.assert_called_with(301)

        actual_length = len(request.getWrittenData())
        reported_length = int(
            request.responseHeaders.getRawHeaders(b'content-length')[0]
        )
        self.assertEqual(reported_length, actual_length)


class ExtractURLpartsTests(TestCase):
    """
    Tests for L{klein.resource._extractURLparts}.
    """
    def test_types(self):
        """
        Returns the correct types.
        """
        url_scheme, server_name, server_port, path_info, script_name = (
            _extractURLparts(requestMock(b"/f\xc3\xb6\xc3\xb6"))
        )

        self.assertIsInstance(url_scheme, unicode)
        self.assertIsInstance(server_name, unicode)
        self.assertIsInstance(server_port, int)
        self.assertIsInstance(path_info, unicode)
        self.assertIsInstance(script_name, unicode)


    def assertDecodingFailure(self, exception, part):
        """
        Checks whether C{exception} consists of a single L{UnicodeDecodeError}
        for C{part}.
        """
        self.assertEqual(1, len(exception.errors))
        actualPart, actualFail = exception.errors[0]
        self.assertEqual(part, actualPart)
        self.assertIsInstance(actualFail.value, UnicodeDecodeError)


    def test_failServerName(self):
        """
        Raises URLDecodeError if SERVER_NAME can't be decoded.
        """
        request = requestMock(b"/foo")
        request.getRequestHostname = lambda: b"f\xc3\xc3\xb6"
        e = self.assertRaises(_URLDecodeError, _extractURLparts, request)
        self.assertDecodingFailure(e, "SERVER_NAME")


    def test_failPathInfo(self):
        """
        Raises URLDecodeError if PATH_INFO can't be decoded.
        """
        request = requestMock(b"/f\xc3\xc3\xb6")
        e = self.assertRaises(_URLDecodeError, _extractURLparts, request)
        self.assertDecodingFailure(e, "PATH_INFO")


    def test_failScriptName(self):
        """
        Raises URLDecodeError if SCRIPT_NAME can't be decoded.
        """
        request = requestMock(b"/foo")
        request.prepath = [b"f\xc3\xc3\xb6"]
        e = self.assertRaises(_URLDecodeError, _extractURLparts, request)
        self.assertDecodingFailure(e, "SCRIPT_NAME")


    def test_failAll(self):
        """
        If multiple parts fail, they all get appended to the errors list of
        URLDecodeError.
        """
        request = requestMock(b"/f\xc3\xc3\xb6")
        request.prepath = [b"f\xc3\xc3\xb6"]
        request.getRequestHostname = lambda: b"f\xc3\xc3\xb6"
        e = self.assertRaises(_URLDecodeError, _extractURLparts, request)
        self.assertEqual(
            set(["SERVER_NAME", "PATH_INFO", "SCRIPT_NAME"]),
            set(part for part, _ in e.errors)
        )

    def test_afUnixSocket(self):
        """
        Test proper handling of AF_UNIX sockets
        """
        request = requestMock(b"/f\xc3\xb6\xc3\xb6")
        server_mock = Mock(Server)
        server_mock.getRequestHostname = u'/var/run/twisted.socket'
        request.host = server_mock
        (
            url_scheme, server_name, server_port, path_info, script_name
        ) = _extractURLparts(request)

        self.assertIsInstance(url_scheme, unicode)
        self.assertIsInstance(server_name, unicode)
        self.assertIsInstance(server_port, int)
        self.assertIsInstance(path_info, unicode)
        self.assertIsInstance(script_name, unicode)


class GlobalAppTests(TestCase):
    """
    Tests for the global app object
    """

    def test_global_app(self):
        from klein import run, route, resource, handle_errors

        globalApp = run.__self__

        self.assertIs(route.__self__, globalApp)
        self.assertIs(resource.__self__, globalApp)
        self.assertIs(handle_errors.__self__, globalApp)

        @route('/')
        def index(request):
            1 // 0

        @handle_errors(ZeroDivisionError)
        def on_zero(request, failure):
            return b'alive'

        request = requestMock(b'/')
        d = _render(resource(), request)
        self.assertIsNone(self.successResultOf(d))
        self.assertEqual(request.getWrittenData(), b'alive')


if _PY3:
    import sys
    if sys.version_info >= (3, 5):
        from .py3_test_resource import PY3KleinResourceTests
        PY3KleinResourceTests  # shh pyflakes
