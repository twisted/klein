import os
from io import BytesIO
from types import MappingProxyType
from typing import Any, Callable, List, Mapping, Optional, Sequence, cast
from unittest.mock import Mock, call
from urllib.parse import parse_qs

from werkzeug.exceptions import NotFound

from twisted.internet.defer import CancelledError, Deferred, fail, succeed
from twisted.internet.error import ConnectionLost
from twisted.internet.interfaces import IProducer
from twisted.internet.unix import Server
from twisted.python.failure import Failure
from twisted.trial.unittest import SynchronousTestCase
from twisted.web.http_headers import Headers
from twisted.web.iweb import IRequest
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET, Request, Site
from twisted.web.static import File
from twisted.web.template import Element, Tag, XMLString, renderer
from twisted.web.test.test_web import DummyChannel

from .. import Klein, KleinRenderable
from .._interfaces import IKleinRequest
from .._resource import (
    KleinResource,
    URLDecodeError,
    ensure_utf8_bytes,
    extractURLparts,
)
from .util import EqualityTestsMixin, recover


emptyMapping: Mapping[Any, Any] = MappingProxyType({})


class MockRequest(Request):
    finished: bool
    startedWriting: bool
    processingFailed: Mock
    setResponseCode: Mock
    setHeader: Mock

    def __init__(
        self,
        path: bytes,
        method: bytes = b"GET",
        host: bytes = b"localhost",
        port: int = 8080,
        isSecure: bool = False,
        body: bytes = b"",
        headers: Mapping[bytes, Sequence[bytes]] = emptyMapping,
    ):
        super().__init__(DummyChannel(), False)

        if not headers:
            headers = {}

        if not body:
            body = b""

        path, qpath = (path.split(b"?", 1) + [b""])[:2]

        self.site = Mock(Site)
        self.gotLength(len(body))
        self.content = BytesIO()
        self.content.write(body)
        self.content.seek(0)
        self.args = parse_qs(qpath)
        self.selfHeaders = Headers(headers)
        self.setHost(host, port, isSecure)
        self.uri = path
        self.prepath: List[bytes] = []
        self.postpath = path.split(b"/")[1:]
        self.method = method
        self.clientproto = b"HTTP/1.1"

        self.setHeader = Mock(wraps=self.setHeader)
        self.setResponseCode = Mock(wraps=self.setResponseCode)

        self._written = BytesIO()
        self.finishCount = 0
        self.writeCount = 0

        self.processingFailed = Mock(wraps=self.processingFailed)

    def registerProducer(self, producer: IProducer, streaming: bool) -> None:
        self.producer = producer
        for _ in range(2):
            if self.producer:
                # typing note: server.Request.registerProducer takes an
                # IProducer, which does not have resumeProducing.
                # This seems to expect either an IPullProducer or an
                # IPushProducer.
                self.producer.resumeProducing()  # type: ignore[attr-defined]

    def unregisterProducer(self) -> None:
        self.producer = None

    def finish(self) -> None:
        self.finishCount += 1

        if not self.startedWriting:
            self.write(b"")

        if not self.finished:
            self.finished = True
            self._cleanup()

    def write(self, data: bytes) -> None:
        self.writeCount += 1
        self.startedWriting = True

        if not self.finished:
            self._written.write(data)
        else:
            raise RuntimeError(
                "Request.write called on a request after "
                "Request.finish was called."
            )

    def getWrittenData(self) -> bytes:
        return self._written.getvalue()


def _render(
    resource: KleinResource, request: IRequest, notifyFinish: bool = True
) -> Deferred:
    result = resource.render(request)

    if isinstance(result, bytes):
        request.write(result)
        request.finish()
        return succeed(None)

    if result is not NOT_DONE_YET:  # type: ignore[comparison-overlap]
        raise AssertionError("unreachable")  # pragma: no cover

    if request.finished or not notifyFinish:  # type: ignore[attr-defined]
        return succeed(None)

    return request.notifyFinish()  # type: ignore[no-any-return,attr-defined]


class SimpleElement(Element):
    loader = XMLString(
        '<h1 xmlns:t="http://twistedmatrix.com/ns/twisted.web.template/0.1" '
        't:render="name" />'
    )

    def __init__(self, name: str) -> None:
        self._name = name

    @renderer
    def name(self, request: IRequest, tag: Tag) -> Tag:
        return tag(self._name)


class DeferredElement(SimpleElement):
    deferred: "Deferred[None]"

    @renderer
    def name(self, request: IRequest, tag: Tag) -> "Deferred[None]":
        self.deferred: "Deferred[None]" = Deferred()
        self.deferred.addCallback(lambda ignored: tag(self._name))
        return self.deferred


class LeafResource(Resource):
    isLeaf = True

    content = b"I am a leaf in the wind."

    def render(self, request: IRequest) -> bytes:
        return self.content


class ChildResource(Resource):
    isLeaf = True

    def __init__(self, name: bytes) -> None:
        self._name = name

    def render(self, request: IRequest) -> bytes:
        return b"I'm a child named " + self._name + b"!"


class ChildrenResource(Resource):
    def render(self, request: IRequest) -> bytes:
        return b"I have children!"

    def getChild(self, path: bytes, request: IRequest) -> Resource:
        if path == b"":
            return self

        return ChildResource(path)


class ProducingResource(Resource):
    def __init__(self, path: bytes, strings: List[bytes]) -> None:
        self.path = path
        self.strings = strings

    def render_GET(self, request: IRequest) -> bytes:
        producer = MockProducer(request, self.strings)
        producer.start()
        # typing note: return type should have been
        # Union[bytes, Literal[NOT_DONE_YET]] but NOT_DONE_YET is an Any
        # right now, so Literal won't accept it.
        return cast(bytes, NOT_DONE_YET)


class MockProducer:
    def __init__(self, request: IRequest, strings: List[bytes]) -> None:
        self.request = request
        self.strings = strings

    def start(self) -> None:
        self.request.registerProducer(self, False)  # type: ignore[attr-defined]

    def resumeProducing(self) -> None:
        if self.strings:
            self.request.write(self.strings.pop(0))
        else:
            self.request.unregisterProducer()  # type: ignore[attr-defined]
            self.request.finish()


class KleinResourceEqualityTests(SynchronousTestCase, EqualityTestsMixin):
    """
    Tests for L{KleinResource}'s implementation of C{==} and C{!=}.
    """

    class _One:
        oneKlein = Klein()

        @oneKlein.route("/foo")
        def foo(self, request: IRequest) -> KleinRenderable:
            pass

    _one = _One()

    class _Another:
        anotherKlein = Klein()

        @anotherKlein.route("/bar")
        def bar(self, request: IRequest) -> KleinRenderable:
            pass

    _another = _Another()

    def anInstance(self) -> Callable[[], KleinResource]:
        return self._one.oneKlein.resource

    def anotherInstance(self) -> Callable[[], KleinResource]:
        return self._another.anotherKlein.resource


class KleinResourceTests(SynchronousTestCase):
    def setUp(self) -> None:
        self.app = Klein()
        self.kr = KleinResource(self.app)

    def assertFired(self, deferred: Deferred, result: object = None) -> None:
        """
        Assert that the given deferred has fired with the given result.
        """
        self.assertEqual(self.successResultOf(deferred), result)

    def assertNotFired(self, deferred: Deferred) -> None:
        """
        Assert that the given deferred has not fired with a result.
        """
        _pawn = object()
        result = getattr(deferred, "result", _pawn)
        if result != _pawn:
            self.fail(
                "Expected deferred not to have fired, but it has: {!r}".format(
                    deferred
                )
            )

    def test_simplePost(self) -> None:
        app = self.app

        # The order in which these functions are defined
        # matters.  If the more generic one is defined first
        # then it will eat requests that should have been handled
        # by the more specific handler.

        @app.route("/", methods=["POST"])
        def handle_post(request: IRequest) -> KleinRenderable:
            return b"posted"

        @app.route("/")
        def handle_default(request: IRequest) -> KleinRenderable:
            return b"gotted"

        request = MockRequest(b"/", b"POST")
        request2 = MockRequest(b"/")

        d = _render(self.kr, request)
        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), b"posted")

        d2 = _render(self.kr, request2)
        self.assertFired(d2)
        self.assertEqual(request2.getWrittenData(), b"gotted")

    def test_simpleRouting(self) -> None:
        app = self.app

        @app.route("/")
        def slash(request: IRequest) -> KleinRenderable:
            return b"ok"

        request = MockRequest(b"/")

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), b"ok")

    def test_branchRendering(self) -> None:
        app = self.app

        @app.route("/", branch=True)
        def slash(request: IRequest) -> KleinRenderable:
            return b"ok"

        request = MockRequest(b"/foo")

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), b"ok")

    def test_branchWithExplicitChildrenRouting(self) -> None:
        app = self.app

        @app.route("/")
        def slash(request: IRequest) -> KleinRenderable:
            return b"ok"

        @app.route("/zeus")
        def wooo(request: IRequest) -> KleinRenderable:
            return b"zeus"

        request = MockRequest(b"/zeus")
        request2 = MockRequest(b"/")

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), b"zeus")

        d2 = _render(self.kr, request2)

        self.assertFired(d2)
        self.assertEqual(request2.getWrittenData(), b"ok")

    def test_branchWithExplicitChildBranch(self) -> None:
        app = self.app

        @app.route("/", branch=True)
        def slash(request: IRequest) -> KleinRenderable:
            return b"ok"

        @app.route("/zeus/", branch=True)
        def wooo(request: IRequest) -> KleinRenderable:
            return b"zeus"

        request = MockRequest(b"/zeus/foo")
        request2 = MockRequest(b"/")

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), b"zeus")

        d2 = _render(self.kr, request2)

        self.assertFired(d2)
        self.assertEqual(request2.getWrittenData(), b"ok")

    def test_deferredRendering(self) -> None:
        app = self.app

        deferredResponse: "Deferred[bytes]" = Deferred()

        @app.route("/deferred")
        def deferred(request: IRequest) -> KleinRenderable:
            return deferredResponse

        request = MockRequest(b"/deferred")

        d = _render(self.kr, request)

        self.assertNotFired(d)

        deferredResponse.callback(b"ok")

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), b"ok")

    def test_asyncRendering(self) -> None:
        app = self.app
        resource = self.kr

        request = MockRequest(b"/resource/leaf")

        @app.route("/resource/leaf")  # type: ignore[arg-type]
        async def leaf(request: IRequest) -> KleinRenderable:
            return LeafResource()

        self.assertFired(_render(resource, request))

        self.assertEqual(request.getWrittenData(), LeafResource.content)

    def test_elementRendering(self) -> None:
        app = self.app

        @app.route("/element/<string:name>")  # type: ignore[arg-type]
        def element(request: IRequest, name: str) -> KleinRenderable:
            return SimpleElement(name)

        request = MockRequest(b"/element/foo")

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(
            request.getWrittenData(), b"<!DOCTYPE html>\n<h1>foo</h1>"
        )

    def test_deferredElementRendering(self) -> None:
        app = self.app

        elements = []

        @app.route("/element/<string:name>")  # type: ignore[arg-type]
        def element(request: IRequest, name: str) -> KleinRenderable:
            it = DeferredElement(name)
            elements.append(it)
            return it

        request = MockRequest(b"/element/bar")

        d = _render(self.kr, request)
        self.assertEqual(len(elements), 1)
        [oneElement] = elements
        self.assertNoResult(d)
        oneElement.deferred.callback(None)
        self.assertFired(d)
        self.assertEqual(
            request.getWrittenData(), b"<!DOCTYPE html>\n<h1>bar</h1>"
        )

    def test_leafResourceRendering(self) -> None:
        app = self.app

        request = MockRequest(b"/resource/leaf")

        @app.route("/resource/leaf")
        def leaf(request: IRequest) -> KleinRenderable:
            return LeafResource()

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), LeafResource.content)

    def test_childResourceRendering(self) -> None:
        app = self.app
        request = MockRequest(b"/resource/children/betty")

        @app.route("/resource/children/", branch=True)
        def children(request: IRequest) -> KleinRenderable:
            return ChildrenResource()

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), b"I'm a child named betty!")

    def test_childrenResourceRendering(self) -> None:
        app = self.app

        request = MockRequest(b"/resource/children/")

        @app.route("/resource/children/", branch=True)
        def children(request: IRequest) -> KleinRenderable:
            return ChildrenResource()

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), b"I have children!")

    def test_producerResourceRendering(self) -> None:
        """
        Test that Klein will correctly handle producing L{Resource}s.

        Producing Resources close the connection by themselves, sometimes after
        Klein has 'finished'. This test lets Klein finish its handling of the
        request before doing more producing.
        """
        app = self.app

        request = MockRequest(b"/resource")

        @app.route("/resource", branch=True)
        def producer(request: IRequest) -> KleinRenderable:
            return ProducingResource(request.uri, [b"a", b"b", b"c", b"d"])

        d = _render(self.kr, request, notifyFinish=False)

        self.assertNotEqual(
            request.getWrittenData(),
            b"abcd",
            "The full response should not have been written at this point.",
        )

        while request.producer:
            request.producer.resumeProducing()

        self.assertEqual(self.successResultOf(d), None)
        self.assertEqual(request.getWrittenData(), b"abcd")
        self.assertEqual(request.writeCount, 4)
        self.assertEqual(request.finishCount, 1)
        self.assertEqual(request.producer, None)

    def test_notFound(self) -> None:
        request = MockRequest(b"/fourohofour")

        d = _render(self.kr, request)

        self.assertFired(d)
        setResponseCode = request.setResponseCode
        setResponseCode.assert_called_with(404)
        self.assertIn(b"404 Not Found", request.getWrittenData())

    def test_renderUnicode(self) -> None:
        app = self.app

        request = MockRequest(b"/snowman")

        @app.route("/snowman")
        def snowman(request: IRequest) -> KleinRenderable:
            return "\u2603"

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), b"\xE2\x98\x83")

    def test_renderNone(self) -> None:
        app = self.app

        request = MockRequest(b"/None")

        @app.route("/None")
        def none(request: IRequest) -> KleinRenderable:
            return None  # type: ignore[return-value]

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), b"")
        self.assertEqual(request.finishCount, 1)
        self.assertEqual(request.writeCount, 1)

    def test_staticRoot(self) -> None:
        app = self.app

        request = MockRequest(b"/__init__.py")
        expected = open(
            os.path.join(os.path.dirname(__file__), "__init__.py"), "rb"
        ).read()

        @app.route("/", branch=True)
        def root(request: IRequest) -> KleinRenderable:
            return File(os.path.dirname(__file__))

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), expected)
        self.assertEqual(request.finishCount, 1)

    def test_explicitStaticBranch(self) -> None:
        app = self.app

        request = MockRequest(b"/static/__init__.py")
        expected = open(
            os.path.join(os.path.dirname(__file__), "__init__.py"), "rb"
        ).read()

        @app.route("/static/", branch=True)
        def root(request: IRequest) -> KleinRenderable:
            return File(os.path.dirname(__file__))

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), expected)
        self.assertEqual(request.writeCount, 1)
        self.assertEqual(request.finishCount, 1)

    def test_staticDirlist(self) -> None:
        app = self.app

        request = MockRequest(b"/")

        @app.route("/", branch=True)
        def root(request: IRequest) -> KleinRenderable:
            return File(os.path.dirname(__file__))

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertIn(b"Directory listing", request.getWrittenData())
        self.assertEqual(request.writeCount, 1)
        self.assertEqual(request.finishCount, 1)

    def test_addSlash(self) -> None:
        app = self.app
        request = MockRequest(b"/foo")

        @app.route("/foo/")
        def foo(request: IRequest) -> KleinRenderable:
            return "foo"

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(
            request.setHeader.call_count,
            3,
        )
        request.setHeader.assert_has_calls(
            [
                call(b"Content-Type", b"text/html; charset=utf-8"),
                call(b"Content-Length", b"258"),
                call(b"Location", b"http://localhost:8080/foo/"),
            ]
        )

    def test_methodNotAllowed(self) -> None:
        app = self.app
        request = MockRequest(b"/foo", method=b"DELETE")

        @app.route("/foo", methods=["GET"])
        def foo(request: IRequest) -> KleinRenderable:
            return "foo"

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.code, 405)

    def test_methodNotAllowedWithRootCollection(self) -> None:
        app = self.app
        request = MockRequest(b"/foo/bar", method=b"DELETE")

        @app.route("/foo/bar", methods=["GET"])
        def foobar(request: IRequest) -> KleinRenderable:
            return b"foo/bar"

        @app.route("/foo/", methods=["DELETE"])
        def foo(request: IRequest) -> KleinRenderable:
            return b"foo"

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.code, 405)

    def test_noImplicitBranch(self) -> None:
        app = self.app
        request = MockRequest(b"/foo")

        @app.route("/")
        def root(request: IRequest) -> KleinRenderable:
            return b"foo"

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.code, 404)

    def test_strictSlashes(self) -> None:
        app = self.app
        request = MockRequest(b"/foo/bar")

        request_url = [None]

        @app.route("/foo/bar/", strict_slashes=False)
        def root(request: IRequest) -> KleinRenderable:
            request_url[0] = request.URLPath()
            return b"foo"

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(str(request_url[0]), "http://localhost:8080/foo/bar")
        self.assertEqual(request.getWrittenData(), b"foo")
        self.assertEqual(request.code, 200)

    def test_URLPath(self) -> None:
        app = self.app
        request = MockRequest(b"/egg/chicken")

        request_url = [None]

        @app.route("/egg/chicken")
        def wooo(request: IRequest) -> KleinRenderable:
            request_url[0] = request.URLPath()
            return b"foo"

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(
            str(request_url[0]), "http://localhost:8080/egg/chicken"
        )

    def test_URLPath_root(self) -> None:
        app = self.app
        request = MockRequest(b"/")

        request_url = [None]

        @app.route("/")
        def root(request: IRequest) -> KleinRenderable:
            request_url[0] = request.URLPath()
            return b""

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(str(request_url[0]), "http://localhost:8080/")

    def test_URLPath_traversedResource(self) -> None:
        app = self.app
        request = MockRequest(b"/resource/foo")

        request_url = [None]

        class URLPathResource(Resource):
            def render(self, request: IRequest) -> KleinRenderable:
                request_url[0] = request.URLPath()
                return b""

            def getChild(  # type: ignore[override]
                self,
                request: IRequest,
                path: bytes,
            ) -> Resource:
                return self

        @app.route("/resource/", branch=True)
        def root(request: IRequest) -> KleinRenderable:
            return URLPathResource()

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(
            str(request_url[0]), "http://localhost:8080/resource/foo"
        )

    def test_handlerRaises(self) -> None:
        app = self.app
        request = MockRequest(b"/")

        failures = []

        class RouteFailureTest(Exception):
            pass

        @app.route("/")
        def root(request: IRequest) -> KleinRenderable:
            def _capture_failure(f: Failure) -> Failure:
                failures.append(f)
                return f

            return fail(RouteFailureTest("die")).addErrback(_capture_failure)

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.code, 500)
        processingFailed = request.processingFailed
        processingFailed.assert_called_once_with(failures[0])
        self.flushLoggedErrors(RouteFailureTest)

    def test_genericErrorHandler(self) -> None:
        app = self.app
        request = MockRequest(b"/")

        failures = []

        class RouteFailureTest(Exception):
            pass

        @app.route("/")
        def root(request: IRequest) -> KleinRenderable:
            raise RouteFailureTest("not implemented")

        @app.handle_errors
        def handle_errors(
            request: IRequest, failure: Failure
        ) -> KleinRenderable:
            failures.append(failure)
            request.setResponseCode(501)
            return b""

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.code, 501)
        assert not request.processingFailed.called

    def test_typeSpecificErrorHandlers(self) -> None:
        app = self.app
        request = MockRequest(b"/")
        type_error_handled = [False]
        generic_error_handled = [False]

        failures = []

        class TypeFilterTestError(Exception):
            pass

        @app.route("/")
        def root(request: IRequest) -> KleinRenderable:
            return fail(TypeFilterTestError("not implemented"))

        @app.handle_errors(TypeError)
        def handle_type_error(
            request: IRequest, failure: Failure
        ) -> KleinRenderable:
            type_error_handled[0] = True
            return b""

        @app.handle_errors(TypeFilterTestError)
        def handle_type_filter_test_error(
            request: IRequest, failure: Failure
        ) -> KleinRenderable:
            failures.append(failure)
            request.setResponseCode(501)
            return b""

        @app.handle_errors
        def handle_generic_error(
            request: IRequest, failure: Failure
        ) -> KleinRenderable:
            generic_error_handled[0] = True
            return b""

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(
            request.processingFailed.called,
            False,
        )
        self.assertEqual(type_error_handled[0], False)
        self.assertEqual(generic_error_handled[0], False)
        self.assertEqual(len(failures), 1)
        self.assertEqual(request.code, 501)

        # Test the above handlers, which otherwise lack test coverage.

        @app.route("/type_error")
        def type_error(request: IRequest) -> KleinRenderable:
            return fail(TypeError("type error"))

        d = _render(self.kr, MockRequest(b"/type_error"))
        self.assertFired(d)
        self.assertEqual(type_error_handled[0], True)

        @app.route("/generic_error")
        def generic_error(request: IRequest) -> KleinRenderable:
            return fail(Exception("generic error"))

        d = _render(self.kr, MockRequest(b"/generic_error"))
        self.assertFired(d)
        self.assertEqual(generic_error_handled[0], True)

    def test_notFoundException(self) -> None:
        app = self.app
        request = MockRequest(b"/")
        generic_error_handled = [False]

        @app.handle_errors(NotFound)
        def handle_not_found(
            request: IRequest, failure: Failure
        ) -> KleinRenderable:
            request.setResponseCode(404)
            return b"Custom Not Found"

        @app.handle_errors
        def handle_generic_error(
            request: IRequest, failure: Failure
        ) -> KleinRenderable:
            generic_error_handled[0] = True
            return b""

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(
            request.processingFailed.called,
            False,
        )
        self.assertEqual(generic_error_handled[0], False)
        self.assertEqual(request.code, 404)
        self.assertEqual(request.getWrittenData(), b"Custom Not Found")
        self.assertEqual(request.writeCount, 1)

        # Test the above handlers, which otherwise lack test coverage.

        @app.route("/generic_error")
        def generic_error(request: IRequest) -> KleinRenderable:
            return fail(Exception("generic error"))

        d = _render(self.kr, MockRequest(b"/generic_error"))
        self.assertFired(d)
        self.assertEqual(generic_error_handled[0], True)

    def test_errorHandlerNeedsRendering(self) -> None:
        """
        Renderables returned by L{handle_errors} are rendered.
        """
        app = self.app
        request = MockRequest(b"/")

        @app.handle_errors(NotFound)
        def handle_not_found(
            request: IRequest, failure: Failure
        ) -> KleinRenderable:
            return SimpleElement("Not Found Element")

        d = _render(self.kr, request)

        rendered = b"<!DOCTYPE html>\n<h1>Not Found Element</h1>"

        self.assertFired(d)
        self.assertEqual(
            request.processingFailed.called,
            False,
        )
        self.assertEqual(request.getWrittenData(), rendered)

    def test_errorHandlerReturnsResource(self) -> None:
        """
        Resources returned by L{Klein.handle_errors} are rendered
        """
        app = self.app
        request = MockRequest(b"/")

        class NotFoundResource(Resource):
            isLeaf = True

            def render(self, request: IRequest) -> KleinRenderable:
                request.setResponseCode(404)
                return b"Nothing found"

        @app.handle_errors(NotFound)
        def handle_not_found(
            request: IRequest, failure: Failure
        ) -> KleinRenderable:
            return NotFoundResource()

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.code, 404)
        self.assertEqual(request.getWrittenData(), b"Nothing found")

    def test_requestWriteAfterFinish(self) -> None:
        app = self.app
        request = MockRequest(b"/")

        @app.route("/")
        def root(request: IRequest) -> KleinRenderable:
            request.finish()
            return b"foo"

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.writeCount, 2)
        self.assertEqual(request.getWrittenData(), b"")
        [failure] = self.flushLoggedErrors(RuntimeError)

        self.assertEqual(
            str(failure.value),
            (
                "Request.write called on a request after Request.finish was "
                "called."
            ),
        )

    def test_requestFinishAfterConnectionLost(self) -> None:
        app = self.app
        request = MockRequest(b"/")

        finished: "Deferred[bytes]" = Deferred()

        @app.route("/")
        def root(request: IRequest) -> KleinRenderable:
            assert isinstance(request, Request)
            request.notifyFinish().addBoth(lambda _: finished.callback(b"foo"))
            return finished

        d = _render(self.kr, request)

        def _eb(result: object) -> None:
            [failure] = self.flushLoggedErrors(RuntimeError)

            self.assertEqual(
                str(failure.value),
                (
                    "Request.finish called on a request after its connection "
                    "was lost; use Request.notifyFinish to keep track of this."
                ),
            )

        d.addErrback(lambda _: finished)
        d.addErrback(_eb)

        self.assertNotFired(d)

        request.connectionLost(ConnectionLost())

        self.assertFired(d)

    def test_routeHandlesRequestFinished(self) -> None:
        app = self.app
        request = MockRequest(b"/")

        cancelled: List[Failure] = []

        @app.route("/")
        def root(request: IRequest) -> KleinRenderable:
            assert isinstance(request, Request)
            _d: "Deferred[bytes]" = Deferred()
            _d.addErrback(cancelled.append)
            request.notifyFinish().addCallback(lambda _: _d.cancel())
            return _d

        d = _render(self.kr, request)

        request.finish()

        self.assertFired(d)

        cancelled[0].trap(CancelledError)
        self.assertEqual(request.getWrittenData(), b"")
        self.assertEqual(request.writeCount, 1)
        self.assertEqual(
            request.processingFailed.call_count,
            0,
        )

    def test_url_for(self) -> None:
        app = self.app
        request = MockRequest(b"/foo/1")

        relative_url: List[str] = ["** ROUTE NOT CALLED **"]

        @app.route("/foo/<int:bar>")  # type: ignore[arg-type]
        def foo(request: IRequest, bar: int) -> KleinRenderable:
            krequest = IKleinRequest(request)
            relative_url[0] = krequest.url_for("foo", {"bar": bar + 1})
            return b""

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(relative_url[0], "/foo/2")

    def test_cancelledDeferred(self) -> None:
        app = self.app
        request = MockRequest(b"/")

        inner_d: "Deferred[bytes]" = Deferred()

        @app.route("/")
        def root(request: IRequest) -> KleinRenderable:
            return inner_d

        d = _render(self.kr, request)

        inner_d.cancel()

        self.assertFired(d)
        self.flushLoggedErrors(CancelledError)

    def test_external_url_for(self) -> None:
        app = self.app
        request = MockRequest(b"/foo/1")

        relative_url: List[Optional[str]] = [None]

        @app.route("/foo/<int:bar>")  # type: ignore[arg-type]
        def foo(request: IRequest, bar: int) -> KleinRenderable:
            krequest = IKleinRequest(request)
            relative_url[0] = krequest.url_for(
                "foo", {"bar": bar + 1}, force_external=True
            )
            return b""

        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(relative_url[0], "http://localhost:8080/foo/2")

    def test_cancelledIsEatenOnConnectionLost(self) -> None:
        app = self.app
        request = MockRequest(b"/")

        @app.route("/")
        def root(request: IRequest) -> KleinRenderable:
            _d: "Deferred[bytes]" = Deferred()
            assert isinstance(request, Request)
            request.notifyFinish().addErrback(lambda _: _d.cancel())
            return _d

        d = _render(self.kr, request)

        self.assertNotFired(d)

        request.connectionLost(ConnectionLost())

        def _cb(result: object) -> None:
            processingFailed = request.processingFailed
            self.assertEqual(
                processingFailed.call_count,
                0,
            )

        d = recover(d, ConnectionLost)
        d.addCallback(_cb)
        self.assertFired(d)

    def test_cancelsOnConnectionLost(self) -> None:
        app = self.app
        request = MockRequest(b"/")

        handler_d: "Deferred[bytes]" = Deferred()

        @app.route("/")
        def root(request: IRequest) -> KleinRenderable:
            return handler_d

        d = _render(self.kr, request)

        self.assertNotFired(d)

        request.connectionLost(ConnectionLost())

        handler_d = recover(handler_d, CancelledError)

        d = recover(d, ConnectionLost)
        d.addCallback(lambda _: handler_d)
        self.assertFired(d)

    def test_ensure_utf8_bytes(self) -> None:
        self.assertEqual(ensure_utf8_bytes("abc"), b"abc")
        self.assertEqual(ensure_utf8_bytes("\u2202"), b"\xe2\x88\x82")
        self.assertEqual(ensure_utf8_bytes(b"\xe2\x88\x82"), b"\xe2\x88\x82")

    def test_decodesPath(self) -> None:
        """
        server_name, path_info, and script_name are decoded as UTF-8 before
        being handed to werkzeug.
        """
        request = MockRequest(b"/f\xc3\xb6\xc3\xb6")

        _render(self.kr, request)
        kreq = IKleinRequest(request)
        self.assertIsInstance(kreq.mapper.server_name, str)
        self.assertIsInstance(kreq.mapper.path_info, str)
        self.assertIsInstance(kreq.mapper.script_name, str)

    def test_failedDecodePathInfo(self) -> None:
        """
        If decoding of one of the URL parts (in this case PATH_INFO) fails, the
        error is logged and 400 returned.
        """
        request = MockRequest(b"/f\xc3\xc3\xb6")
        _render(self.kr, request)
        rv = request.getWrittenData()
        self.assertEqual(b"Non-UTF-8 encoding in URL.", rv)
        self.assertEqual(1, len(self.flushLoggedErrors(UnicodeDecodeError)))

    def test_urlDecodeErrorRepr(self) -> None:
        """
        URLDecodeError.__repr__ formats properly.
        """
        try:
            raise ValueError("value")
        except ValueError:
            valueFailure = Failure()

        try:
            raise TypeError("type")
        except TypeError:
            typeFailure = Failure()

        error = URLDecodeError([("VALUE", valueFailure), ("TYPE", typeFailure)])
        self.assertEqual(
            "<URLDecodeError(errors=["
            "('VALUE', "
            "<twisted.python.failure.Failure builtins.ValueError: value>), "
            "('TYPE', "
            "<twisted.python.failure.Failure builtins.TypeError: type>)])>",
            repr(error),
        )

    def test_subroutedBranch(self) -> None:
        subapp = Klein()

        @subapp.route("/foo")
        def foo(request: IRequest) -> KleinRenderable:
            return b"foo"

        app = self.app
        with app.subroute("/sub") as app:

            @app.route("/app", branch=True)
            def subapp_endpoint(request: IRequest) -> KleinRenderable:
                return subapp.resource()

        request = MockRequest(b"/sub/app/foo")
        d = _render(self.kr, request)

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), b"foo")

    def test_correctContentLengthForRequestRedirect(self) -> None:
        app = self.app

        @app.route("/alias", alias=True)
        @app.route("/real")
        def real(request: IRequest) -> KleinRenderable:
            return b"42"

        request = MockRequest(b"/real")
        d = _render(self.kr, request)
        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), b"42")

        request = MockRequest(b"/alias")
        d = _render(self.kr, request)
        self.assertFired(d)
        # Werkzeug switched the redirect status code used from 301 to 308.
        # Both are valid here.
        self.assertIn(
            request.setResponseCode.call_args[0],
            [(301,), (308,)],
        )

        actual_length = len(request.getWrittenData())
        values = request.responseHeaders.getRawHeaders(b"content-length")
        assert values is not None
        reported_length = int(values[0])
        self.assertEqual(reported_length, actual_length)


class ExtractURLpartsTests(SynchronousTestCase):
    """
    Tests for L{klein.resource.extractURLparts}.
    """

    def test_types(self) -> None:
        """
        Returns the correct types.
        """
        (
            url_scheme,
            server_name,
            server_port,
            path_info,
            script_name,
        ) = extractURLparts(MockRequest(b"/f\xc3\xb6\xc3\xb6"))

        self.assertIsInstance(url_scheme, str)
        self.assertIsInstance(server_name, str)
        self.assertIsInstance(server_port, int)
        self.assertIsInstance(path_info, str)
        self.assertIsInstance(script_name, str)

    def assertDecodingFailure(
        self, exception: URLDecodeError, part: str
    ) -> None:
        """
        Checks whether C{exception} consists of a single L{UnicodeDecodeError}
        for C{part}.
        """
        self.assertEqual(1, len(exception.errors))
        actualPart, actualFail = exception.errors[0]
        self.assertEqual(part, actualPart)
        self.assertIsInstance(actualFail.value, UnicodeDecodeError)

    def test_failServerName(self) -> None:
        """
        Raises URLDecodeError if SERVER_NAME can't be decoded.
        """
        request = MockRequest(b"/foo")
        request.getRequestHostname = (  # type: ignore[assignment]
            lambda: b"f\xc3\xc3\xb6"
        )
        e = self.assertRaises(URLDecodeError, extractURLparts, request)
        self.assertDecodingFailure(e, "SERVER_NAME")

    def test_failPathInfo(self) -> None:
        """
        Raises URLDecodeError if PATH_INFO can't be decoded.
        """
        request = MockRequest(b"/f\xc3\xc3\xb6")
        e = self.assertRaises(URLDecodeError, extractURLparts, request)
        self.assertDecodingFailure(e, "PATH_INFO")

    def test_failScriptName(self) -> None:
        """
        Raises URLDecodeError if SCRIPT_NAME can't be decoded.
        """
        request = MockRequest(b"/foo")
        request.prepath = [b"f\xc3\xc3\xb6"]
        e = self.assertRaises(URLDecodeError, extractURLparts, request)
        self.assertDecodingFailure(e, "SCRIPT_NAME")

    def test_failAll(self) -> None:
        """
        If multiple parts fail, they all get appended to the errors list of
        URLDecodeError.
        """
        request = MockRequest(b"/f\xc3\xc3\xb6")
        request.prepath = [b"f\xc3\xc3\xb6"]
        request.getRequestHostname = (  # type: ignore[assignment]
            lambda: b"f\xc3\xc3\xb6"
        )
        e = self.assertRaises(URLDecodeError, extractURLparts, request)
        self.assertEqual(
            {"SERVER_NAME", "PATH_INFO", "SCRIPT_NAME"},
            {part for part, _ in e.errors},
        )

    def test_afUnixSocket(self) -> None:
        """
        Test proper handling of AF_UNIX sockets
        """
        request = MockRequest(b"/f\xc3\xb6\xc3\xb6")
        server_mock = Mock(Server)
        server_mock.getRequestHostname = "/var/run/twisted.socket"
        request.host = server_mock
        (
            url_scheme,
            server_name,
            server_port,
            path_info,
            script_name,
        ) = extractURLparts(request)

        self.assertIsInstance(url_scheme, str)
        self.assertIsInstance(server_name, str)
        self.assertIsInstance(server_port, int)
        self.assertIsInstance(path_info, str)
        self.assertIsInstance(script_name, str)


class GlobalAppTests(SynchronousTestCase):
    """
    Tests for the global app object
    """

    def test_global_app(self) -> None:
        from klein.app import handle_errors, resource, route, run

        globalApp = run.__self__  # type: ignore[attr-defined]

        self.assertIs(
            route.__self__,  # type: ignore[attr-defined]
            globalApp,
        )
        self.assertIs(
            resource.__self__,  # type: ignore[attr-defined]
            globalApp,
        )
        self.assertIs(
            handle_errors.__self__,  # type: ignore[attr-defined]
            globalApp,
        )

        @route("/")
        def index(request: IRequest) -> KleinRenderable:
            raise RuntimeError("oops")

        @handle_errors(RuntimeError)
        def on_zero(request: IRequest, failure: Failure) -> KleinRenderable:
            return b"alive"

        request = MockRequest(b"/")
        d = _render(resource(), request)
        self.assertIsNone(self.successResultOf(d))
        self.assertEqual(request.getWrittenData(), b"alive")

    def test_weird_resource_situation(self) -> None:
        """
        Historically, the object named "C{klein.resource}" has had two
        meanings:

            - One is "C{klein.*} is sort of like a C{klein.Klein} instance, so
              C{klein.resource()} is sort of like C{klein.Klein.resource()}".

            - The other is "the public module in which
              C{klein.resource.KleinResource} is defined".

        This used to only work by accident; these meanings both sort of worked
        but only as long as you followed a certain import convention (C{from
        klein import resource} for the former, C{from klein.resource import
        KleinResource} for the latter).  This test ensures that
        C{klein.resource} is a special object, callable as you would expect
        from the former, but also having the attributes of the latter.
        """
        from klein import resource
        from klein.resource import KleinResource, ensure_utf8_bytes

        self.assertEqual(
            repr(resource), "<special bound method/module klein.resource>"
        )
        self.assertIdentical(resource.KleinResource, KleinResource)
        self.assertIdentical(resource.ensure_utf8_bytes, ensure_utf8_bytes)
