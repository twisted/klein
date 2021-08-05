"""
Tests for exported API.
"""

from twisted.trial import unittest


class PublicSymbolsTestCase(unittest.TestCase):
    """
    Tests for public API modules.
    """

    def test_klein(self) -> None:
        """
        Test exports from L{klein}.
        """
        import klein as k
        import klein._app as a
        import klein._plating as p

        self.assertIdentical(k.Klein, a.Klein)
        self.assertIdentical(k.handle_errors, a.handle_errors)
        self.assertIdentical(k.route, a.route)
        self.assertIdentical(k.run, a.run)

        self.assertIdentical(k.Plating, p.Plating)

    def test_klein_resource(self) -> None:
        """
        Test export of C{resource} from L{klein}.
        """
        import klein as k
        import klein._app as a

        self.assertIdentical(k.resource()._app, a.resource()._app)

    def test_app(self) -> None:
        """
        Test exports from L{klein.app}.
        """
        import klein._app as _a
        import klein.app as a

        self.assertIdentical(a.Klein, _a.Klein)
        self.assertIdentical(a.KleinRequest, _a.KleinRequest)
        self.assertIdentical(a.handle_errors, _a.handle_errors)
        self.assertIdentical(a.route, _a.route)
        self.assertIdentical(a.run, _a.run)

    def test_interfaces(self) -> None:
        """
        Test exports from L{klein.interfaces}.
        """
        import klein._interfaces as _i
        import klein.interfaces as i

        self.assertIdentical(i.IKleinRequest, _i.IKleinRequest)

    def test_resource(self) -> None:
        """
        Test exports from L{klein.resource}.
        """
        import klein._resource as _r
        import klein.resource as r

        self.assertIdentical(r.KleinResource, _r.KleinResource)
        self.assertIdentical(r.ensure_utf8_bytes, _r.ensure_utf8_bytes)
