from __future__ import absolute_import, division

import sys

from mock import Mock, patch

from twisted.python.components import registerAdapter
from twisted.trial import unittest

from klein import Klein
from klein._decorators import bindable, modified, originalName
from klein.app import KleinRequest
from klein.interfaces import IKleinRequest
from klein.test.util import EqualityTestsMixin



class DummyRequest(object):
    def __init__(self, n):
        self.n = n

    def __eq__(self, other):
        return other.n == self.n

    def __repr__(self):
        return '<DummyRequest({n})>'.format(n=self.n)


registerAdapter(KleinRequest, DummyRequest, IKleinRequest)


class KleinEqualityTestCase(unittest.TestCase, EqualityTestsMixin):
    """
    Tests for L{Klein}'s implementation of C{==} and C{!=}.
    """
    class _One(object):
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
        self.assertEqual(
            c.match("/sub/prefixed_uri"), ("foo_endpoint", {}))
        self.assertEqual(
            len(app.endpoints), 1)
        self.assertEqual(
            app.execute_endpoint("foo_endpoint", DummyRequest(1)), b"foo")


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
        self.assertEqual(
            app.execute_endpoint("bar", DummyRequest(2)), "foobar"
        )


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
            c.match("/foo/bar"),
            ("branchfunc_branch", {'__rest__': 'bar'}))

        self.assertEquals(app.endpoints["branchfunc"].__name__,
                          "route '/foo/' executor for branchfunc")
        self.assertEquals(
            app.endpoints["branchfunc_branch"].__name__,
            "branch route '/foo/' executor for branchfunc"
        )
        self.assertEquals(
            app.execute_endpoint("branchfunc_branch",
                                 DummyRequest("looking for foo")),
            "foo"
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

        req = object()
        k.execute_endpoint("method", req)

        class BoundTo(object):
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
        self.assertEqual(add.supersized, True)
        self.assertIn("supersizer for add", str(megaAdd))
        self.assertEqual(megaAdd(3, 4), 43000)


    def test_classicalRoute(self):
        """
        L{Klein.route} may be used a method decorator when a L{Klein} instance
        is defined as a class variable.
        """
        bar_calls = []

        class Foo(object):
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
        class Foo(object):
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

        foo_1_app.execute_endpoint('bar', dr1)
        foo_2_app.execute_endpoint('bar', dr2)

        self.assertEqual(foo_1.bar_calls, [(foo_1, dr1)])
        self.assertEqual(foo_2.bar_calls, [(foo_2, dr2)])


    def test_classicalRouteWithBranch(self):
        """
        Multiple instances of a class with a L{Klein} attribute and
        L{Klein.route}'d methods can be created and their L{Klein}s used
        independently.
        """
        class Foo(object):
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

        foo_1_app.execute_endpoint('bar_branch', dr1)
        foo_2_app.execute_endpoint('bar_branch', dr2)

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
        self.assertEqual(c.match("/foo/bar"),
                         ("foo_branch", {"__rest__": "bar"}))


    @patch('klein.app.KleinResource')
    @patch('klein.app.Site')
    @patch('klein.app.log')
    @patch('klein.app.reactor')
    def test_run(self, reactor, mock_log, mock_site, mock_kr):
        """
        L{Klein.run} configures a L{KleinResource} and a L{Site}
        listening on the specified interface and port, and logs
        to stdout.
        """
        app = Klein()

        app.run("localhost", 8080)

        reactor.listenTCP.assert_called_with(
            8080, mock_site.return_value, backlog=50, interface="localhost")

        reactor.run.assert_called_with()

        mock_site.assert_called_with(mock_kr.return_value)
        mock_kr.assert_called_with(app)
        mock_log.startLogging.assert_called_with(sys.stdout)


    @patch('klein.app.KleinResource')
    @patch('klein.app.Site')
    @patch('klein.app.log')
    @patch('klein.app.reactor')
    def test_runWithLogFile(self, reactor, mock_log, mock_site, mock_kr):
        """
        L{Klein.run} logs to the specified C{logFile}.
        """
        app = Klein()

        logFile = Mock()
        app.run("localhost", 8080, logFile=logFile)

        reactor.listenTCP.assert_called_with(
            8080, mock_site.return_value, backlog=50, interface="localhost")

        reactor.run.assert_called_with()

        mock_site.assert_called_with(mock_kr.return_value)
        mock_kr.assert_called_with(app)
        mock_log.startLogging.assert_called_with(logFile)


    @patch('klein.app.KleinResource')
    @patch('klein.app.log')
    @patch('klein.app.endpoints.serverFromString')
    @patch('klein.app.reactor')
    def test_runTCP6(self, reactor, mock_sfs, mock_log, mock_kr):
        """
        L{Klein.run} called with tcp6 endpoint description.
        """
        app = Klein()
        interface = "2001\:0DB8\:f00e\:eb00\:\:1"
        spec = "tcp6:8080:interface={0}".format(interface)
        app.run(endpoint_description=spec)
        reactor.run.assert_called_with()
        mock_sfs.assert_called_with(reactor, spec)
        mock_log.startLogging.assert_called_with(sys.stdout)
        mock_kr.assert_called_with(app)


    @patch('klein.app.KleinResource')
    @patch('klein.app.log')
    @patch('klein.app.endpoints.serverFromString')
    @patch('klein.app.reactor')
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
        mock_log.startLogging.assert_called_with(sys.stdout)
        mock_kr.assert_called_with(app)


    @patch('klein.app.KleinResource')
    def test_resource(self, mock_kr):
        """
        L{Klien.resource} returns a L{KleinResource}.
        """
        app = Klein()
        resource = app.resource()

        mock_kr.assert_called_with(app)
        self.assertEqual(mock_kr.return_value, resource)
