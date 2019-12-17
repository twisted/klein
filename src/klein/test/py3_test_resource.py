from twisted.trial.unittest import TestCase as AsynchronousTestCase

from .test_resource import LeafResource, _render, requestMock
from .. import Klein
from .._resource import KleinResource


class PY3KleinResourceTests(AsynchronousTestCase):
    def assertFired(self, deferred, result=None):
        """
        Assert that the given deferred has fired with the given result.
        """
        self.assertEqual(self.successResultOf(deferred), result)

    def test_asyncResourceRendering(self):
        app = Klein()
        resource = KleinResource(app)

        request = requestMock(b"/resource/leaf")

        @app.route("/resource/leaf")
        async def leaf(request):
            return LeafResource()

        expected = b"I am a leaf in the wind."

        d = _render(resource, request)

        def assertResult(_):
            self.assertEqual(request.getWrittenData(), expected)

        d.addCallback(assertResult)

        return d
