from sys import stdout
from typing import cast
from unittest.mock import Mock, patch

from zope.interface import implementer

from twisted.python.components import registerAdapter
from twisted.trial import unittest
from twisted.web.iweb import IRequest

from .. import Klein
from .._app import KleinRequest
from .._decorators import bindable, modified, originalName
from .._interfaces import IKleinRequest
from .test_resource import MockRequest
from .util import EqualityTestsMixin


@implementer(IRequest)
class DummyRequest:  # type: ignore[misc]  # incomplete interface
    def __init__(self, n):
        self.n = n

    def __eq__(self, other):
        return other.n == self.n


registerAdapter(KleinRequest, DummyRequest, IKleinRequest)


class KleinEqualityTestCase(unittest.TestCase, EqualityTestsMixin):
    """
    Tests for L{Klein}'s implementation of C{==} and C{!=}.
    """

    class _One:
        app = Klein()

        def __eq__(self, other):
            return True

        def __ne__(self, other):
            return False

        def __hash__(self):
            return id(self)

    _another = Klein()

    def anInstance(self):
        # This is actually a new Klein instance every time since Klein.__get__
        # creates a new Klein instance for every instance it is retrieved from.
        # The different _One instance, at least, will not cause the Klein
        # instances to be not-equal to each other since an instance of _One is
        # equal to everything.
        return self._One().app

    def anotherInstance(self):
        return self._another


class DuplicateHasher:
    """
    Every L{DuplicateHasher} has the same hash value and compares equal to
    every other L{DuplicateHasher}.
    """

    __slots__ = ("_identifier",)

    def __init__(self, identifier):
        self._identifier = identifier

    myRouter = Klein()

    @myRouter.route("/")
    def root(self, request):
        return self._identifier

    def __hash__(self):
        return 1

    def __eq__(self, other):
        return True


class KleinTestCase(unittest.TestCase):
    def test_route(self):
        """
        L{Klein.route} adds functions as routable endpoints.
        """
        app = Klein()

        @app.route("/foo")
        def foo(request):
            return "foo"

        c = app.url_map.bind("foo")
        self.assertEqual(c.match("/foo"), ("foo", {}))
        self.assertEqual(len(app.endpoints), 1)

        self.assertEqual(app.execute_endpoint("foo", DummyRequest(1)), "foo")

    def test_mapByIdentity(self):
        """
        Routes are routed to the proper object regardless of its C{__hash__}
        implementation.
        """
        a = DuplicateHasher("a")
        b = DuplicateHasher("b")

        # Sanity check
        d = {}
        d[a] = "test"
        self.assertEqual(d.get(b), "test")

        self.assertEqual(
            a.myRouter.execute_endpoint("root", DummyRequest(1)), "a"
        )
        self.assertEqual(
            b.myRouter.execute_endpoint("root", DummyRequest(1)), "b"
        )

    def test_preserveIdentityWhenPossible(self):
        """
        Repeated accesses of the same L{Klein} attribute on the same instance
        should result in an identically bound instance, when possible.
        "Possible" is defined by a writable instance-level attribute named
        C{__klein_bound_<the name of the Klein attribute on the class>__}, and
        something is maintaining a strong reference to the L{Klein} instance.
        """
        # This is the desirable property.
        class DuplicateHasherWithWritableAttribute(DuplicateHasher):
            __slots__ = ("__klein_bound_myRouter__",)

        a = DuplicateHasherWithWritableAttribute("a")
        self.assertIs(a.myRouter, a.myRouter)

        b = DuplicateHasher("b")
        # The following is simply an unfortunate consequence of the
        # implementation choice here (i.e.: to insist on a specific writable
        # attribute), and could be changed (for example, by doing something
        # more elaborate with the identity of the object containing the
        # router).  However, checking this also sets a sort of bounded "worst
        # case" scenario"; it still works, nobody raises an exception, it's
        # just not identical.
        self.assertIsNot(b.myRouter, b.myRouter)

    def test_kleinNotFoundOnClass(self):
        """
        When the Klein object can't find itself on the class it still preserves
        identity.
        """

        class Wrap:
            def __init__(self, wrapped):
                self._wrapped = wrapped

            def __get__(self, instance, owner):
                if instance is None:
                    return self
                return self._wrapped.__get__(instance, owner)

        class TwoRouters:

            app1 = Wrap(Klein())
            app2 = Wrap(Klein())

        tr = TwoRouters()

        self.assertIs(tr.app1, tr.app1)
        self.assertIs(tr.app2, tr.app2)

    def test_bindInstanceIgnoresBlankProperties(self):
        """
        L{Klein.__get__} doesn't propagate L{AttributeError} when
        searching for the bound L{Klein} instance.
        """

        class ClassProperty:
            def __get__(self, oself, owner):
                raise AttributeError(
                    "you just don't have that special something"
                )

        class Oddment:
            __something__ = ClassProperty()
            app = Klein()

        self.assertIsInstance(Oddment().app, Klein)

    def test_submountedRoute(self):
        """
        L{Klein.subroute} adds functions as routable endpoints.
        """
        app = Klein()

        with app.subroute("/sub") as app:

            @app.route("/prefixed_uri")
            def foo_endpoint(request):
                return b"foo"

        c = app.url_map.bind("sub/prefixed_uri")
        self.assertEqual(c.match("/sub/prefixed_uri"), ("foo_endpoint", {}))
        self.assertEqual(len(app.endpoints), 1)
        self.assertEqual(
            app.execute_endpoint("foo_endpoint", DummyRequest(1)), b"foo"
        )

    def test_stackedRoute(self):
        """
        L{Klein.route} can be stacked to create multiple endpoints of a single
        function.
        """
        app = Klein()

        @app.route("/foo")
        @app.route("/bar", endpoint="bar")
        def foobar(request):
            return "foobar"

        self.assertEqual(len(app.endpoints), 2)

        c = app.url_map.bind("foo")
        self.assertEqual(c.match("/foo"), ("foobar", {}))
        self.assertEqual(
            app.execute_endpoint("foobar", DummyRequest(1)), "foobar"
        )

        self.assertEqual(c.match("/bar"), ("bar", {}))
        self.assertEqual(app.execute_endpoint("bar", DummyRequest(2)), "foobar")

    def test_branchRoute(self):
        """
        L{Klein.route} should create a branch path which consumes all children
        when the branch keyword argument is True.
        """
        app = Klein()

        @app.route("/foo/", branch=True)
        def branchfunc(request):
            return "foo"

        c = app.url_map.bind("foo")
        self.assertEqual(c.match("/foo/"), ("branchfunc", {}))
        self.assertEqual(
            c.match("/foo/bar"), ("branchfunc_branch", {"__rest__": "bar"})
        )

        self.assertEquals(
            app.endpoints["branchfunc"].__name__,  # type: ignore[union-attr]
            "route '/foo/' executor for branchfunc",
        )
        self.assertEquals(
            app.endpoints[
                "branchfunc_branch"
            ].__name__,  # type: ignore[union-attr]
            "branch route '/foo/' executor for branchfunc",
        )
        self.assertEquals(
            app.execute_endpoint(
                "branchfunc_branch", DummyRequest("looking for foo")
            ),
            "foo",
        )

    def test_bindable(self):
        """
        L{bindable} is a decorator which allows a function decorated by @route
        to have a uniform signature regardless of whether it is receiving a
        bound object from its L{Klein} or not.
        """
        k = Klein()
        calls = []

        @k.route("/test")
        @bindable
        def method(*args):
            calls.append(args)
            return 7

        req = cast(IRequest, object())
        k.execute_endpoint("method", req)

        class BoundTo:
            app = k

        b = BoundTo()
        b.app.execute_endpoint("method", req)

        self.assertEquals(calls, [(None, req), (b, req)])
        self.assertEqual(originalName(method), "method")

    def test_modified(self):
        """
        L{modified} is a decorator which alters the thing that it decorates,
        and describes itself as such.
        """

        def annotate(decoratee):
            decoratee.supersized = True
            return decoratee

        def add(a, b):
            return a + b

        @modified("supersizer", add, modifier=annotate)
        def megaAdd(a, b):
            return add(a * 1000, b * 10000)

        self.assertEqual(megaAdd.supersized, True)
        self.assertEqual(add.supersized, True)  # type: ignore[attr-defined]
        self.assertIn("supersizer for add", str(megaAdd))
        self.assertEqual(megaAdd(3, 4), 43000)

    def test_classicalRoute(self):
        """
        L{Klein.route} may be used a method decorator when a L{Klein} instance
        is defined as a class variable.
        """
        bar_calls = []

        class Foo:
            app = Klein()

            @app.route("/bar")
            def bar(self, request):
                bar_calls.append((self, request))
                return "bar"

        foo = Foo()
        c = foo.app.url_map.bind("bar")

        self.assertEqual(c.match("/bar"), ("bar", {}))
        self.assertEqual(
            foo.app.execute_endpoint("bar", DummyRequest(1)), "bar"
        )
        self.assertEqual(bar_calls, [(foo, DummyRequest(1))])

    def test_classicalRouteWithTwoInstances(self):
        """
        Multiple instances of a class with a L{Klein} attribute and
        L{Klein.route}'d methods can be created and their L{Klein}s used
        independently.
        """

        class Foo:
            app = Klein()

            def __init__(self):
                self.bar_calls = []

            @app.route("/bar")
            def bar(self, request):
                self.bar_calls.append((self, request))
                return "bar"

        foo_1 = Foo()
        foo_1_app = foo_1.app
        foo_2 = Foo()
        foo_2_app = foo_2.app

        dr1 = DummyRequest(1)
        dr2 = DummyRequest(2)

        foo_1_app.execute_endpoint("bar", dr1)
        foo_2_app.execute_endpoint("bar", dr2)

        self.assertEqual(foo_1.bar_calls, [(foo_1, dr1)])
        self.assertEqual(foo_2.bar_calls, [(foo_2, dr2)])

    def test_classicalRouteWithBranch(self):
        """
        Multiple instances of a class with a L{Klein} attribute and
        L{Klein.route}'d methods can be created and their L{Klein}s used
        independently.
        """

        class Foo:
            app = Klein()

            def __init__(self):
                self.bar_calls = []

            @app.route("/bar/", branch=True)
            def bar(self, request):
                self.bar_calls.append((self, request))
                return "bar"

        foo_1 = Foo()
        foo_1_app = foo_1.app
        foo_2 = Foo()
        foo_2_app = foo_2.app

        dr1 = DummyRequest(1)
        dr2 = DummyRequest(2)

        foo_1_app.execute_endpoint("bar_branch", dr1)
        foo_2_app.execute_endpoint("bar_branch", dr2)

        self.assertEqual(foo_1.bar_calls, [(foo_1, dr1)])
        self.assertEqual(foo_2.bar_calls, [(foo_2, dr2)])

    def test_branchDoesntRequireTrailingSlash(self):
        """
        L{Klein.route} should create a branch path which consumes all children,
        when the branch keyword argument is True and there is no trailing /
        on the path.
        """
        app = Klein()

        @app.route("/foo", branch=True)
        def foo(request):
            return "foo"

        c = app.url_map.bind("foo")
        self.assertEqual(
            c.match("/foo/bar"), ("foo_branch", {"__rest__": "bar"})
        )

    @patch("klein._app.KleinResource")
    @patch("klein._app.Site")
    @patch("klein._app.log")
    @patch("klein._app.reactor")
    def test_run(self, reactor, mock_log, mock_site, mock_kr):
        """
        L{Klein.run} configures a L{KleinResource} and a L{Site}
        listening on the specified interface and port, and logs
        to stdout.
        """
        app = Klein()

        app.run("localhost", 8080)

        reactor.listenTCP.assert_called_with(
            8080, mock_site.return_value, backlog=50, interface="localhost"
        )

        reactor.run.assert_called_with()

        mock_site.assert_called_with(mock_kr.return_value)
        mock_kr.assert_called_with(app)
        mock_log.startLogging.assert_called_with(stdout)

    @patch("klein._app.KleinResource")
    @patch("klein._app.Site")
    @patch("klein._app.log")
    @patch("klein._app.reactor")
    def test_runWithLogFile(self, reactor, mock_log, mock_site, mock_kr):
        """
        L{Klein.run} logs to the specified C{logFile}.
        """
        app = Klein()

        logFile = Mock()
        app.run("localhost", 8080, logFile=logFile)

        reactor.listenTCP.assert_called_with(
            8080, mock_site.return_value, backlog=50, interface="localhost"
        )

        reactor.run.assert_called_with()

        mock_site.assert_called_with(mock_kr.return_value)
        mock_kr.assert_called_with(app)
        mock_log.startLogging.assert_called_with(logFile)

    @patch("klein._app.KleinResource")
    @patch("klein._app.log")
    @patch("klein._app.serverFromString")
    @patch("klein._app.reactor")
    def test_runTCP6(self, reactor, mock_sfs, mock_log, mock_kr):
        """
        L{Klein.run} called with tcp6 endpoint description.
        """
        app = Klein()
        interface = "2001\\:0DB8\\:f00e\\:eb00\\:\\:1"
        spec = f"tcp6:8080:interface={interface}"
        app.run(endpoint_description=spec)
        reactor.run.assert_called_with()
        mock_sfs.assert_called_with(reactor, spec)
        mock_log.startLogging.assert_called_with(stdout)
        mock_kr.assert_called_with(app)

    @patch("klein._app.KleinResource")
    @patch("klein._app.log")
    @patch("klein._app.serverFromString")
    @patch("klein._app.reactor")
    def test_runSSL(self, reactor, mock_sfs, mock_log, mock_kr):
        """
        L{Klein.run} called with SSL endpoint specification.
        """
        app = Klein()
        key = "key.pem"
        cert = "cert.pem"
        dh_params = "dhparam.pem"
        spec_template = "ssl:443:privateKey={0}:certKey={1}"
        spec = spec_template.format(key, cert, dh_params)
        app.run(endpoint_description=spec)
        reactor.run.assert_called_with()
        mock_sfs.assert_called_with(reactor, spec)
        mock_log.startLogging.assert_called_with(stdout)
        mock_kr.assert_called_with(app)

    @patch("klein._app.KleinResource")
    def test_resource(self, mock_kr):
        """
        L{Klien.resource} returns a L{KleinResource}.
        """
        app = Klein()
        resource = app.resource()

        mock_kr.assert_called_with(app)
        self.assertEqual(mock_kr.return_value, resource)

    def test_urlFor(self):
        """L{Klein.urlFor} builds an URL for an endpoint with parameters"""

        app = Klein()

        @app.route("/user/<name>")
        def userpage(req, name):
            return name

        @app.route("/post/<int:postid>", endpoint="bar")
        def foo(req, postid):
            return str(postid)

        request = MockRequest(b"/user/john")
        self.assertEqual(
            app.execute_endpoint("userpage", request, "john"), "john"
        )
        self.assertEqual(
            app.execute_endpoint("bar", MockRequest(b"/post/123"), 123), "123"
        )

        request = MockRequest(b"/addr")
        self.assertEqual(
            app.urlFor(request, "userpage", {"name": "john"}), "/user/john"
        )

        request = MockRequest(b"/addr")
        self.assertEqual(
            app.urlFor(
                request, "userpage", {"name": "john"}, force_external=True
            ),
            "http://localhost:8080/user/john",
        )

        request = MockRequest(b"/addr", host=b"example.com", port=4321)
        self.assertEqual(
            app.urlFor(
                request, "userpage", {"name": "john"}, force_external=True
            ),
            "http://example.com:4321/user/john",
        )

        request = MockRequest(b"/addr")
        url = app.urlFor(
            request,
            "userpage",
            {"name": "john", "age": 29},
            append_unknown=True,
        )
        self.assertEqual(url, "/user/john?age=29")

        request = MockRequest(b"/addr")
        self.assertEqual(
            app.urlFor(request, "bar", {"postid": 123}), "/post/123"
        )

        request = MockRequest(b"/addr")
        request.requestHeaders.removeHeader(b"host")
        self.assertEqual(
            app.urlFor(request, "bar", {"postid": 123}), "/post/123"
        )

        request = MockRequest(b"/addr")
        request.requestHeaders.removeHeader(b"host")
        with self.assertRaises(ValueError):
            app.urlFor(request, "bar", {"postid": 123}, force_external=True)
