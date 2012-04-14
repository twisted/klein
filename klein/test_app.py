from twisted.trial import unittest

import sys

from mock import Mock, patch

from klein import Klein


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
        self.assertIdentical(app.endpoints["foo"], foo)

        self.assertEqual(app.endpoints["foo"](None), "foo")


    def test_stackedRoute(self):
        """
        L{Klein.route} can be stacked to create multiple endpoints of
        a single function.
        """
        app = Klein()

        @app.route("/foo")
        @app.route("/bar", endpoint="bar")
        def foobar(request):
            return "foobar"

        self.assertEqual(len(app.endpoints), 2)

        c = app.url_map.bind("foo")
        self.assertEqual(c.match("/foo"), ("foobar", {}))
        self.assertIdentical(app.endpoints["foobar"], foobar)

        self.assertEqual(c.match("/bar"), ("bar", {}))
        self.assertIdentical(app.endpoints["foobar"], foobar)

        self.assertEqual(app.endpoints["foobar"](None), "foobar")


    def test_branchRoute(self):
        """
        L{Klein.route} should create a branch path which consumes all children
        when the URL has a trailing '/'
        """
        app = Klein()

        @app.route("/foo/")
        def foo(request):
            return "foo"

        c = app.url_map.bind("foo")
        self.assertEqual(c.match("/foo/"), ("foo", {}))
        self.assertEqual(
            c.match("/foo/bar"),
            ("foo_branch", {'__rest__': 'bar'}))

        self.assertIdentical(app.endpoints["foo"], foo)
        self.assertNotIdentical(app.endpoints["foo_branch"], foo)
        self.assertEquals(
            app.endpoints["foo"].__name__,
            app.endpoints["foo"].__name__)


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
            8080, mock_site.return_value, interface="localhost")

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
            8080, mock_site.return_value, interface="localhost")

        reactor.run.assert_called_with()

        mock_site.assert_called_with(mock_kr.return_value)
        mock_kr.assert_called_with(app)
        mock_log.startLogging.assert_called_with(logFile)


    @patch('klein.app.KleinResource')
    def test_resource(self, mock_kr):
        """
        L{Klien.resource} returns a L{KleinResource}.
        """
        app = Klein()
        resource = app.resource()

        mock_kr.assert_called_with(app)
        self.assertEqual(mock_kr.return_value, resource)
