from klein import Klein
from klein.resource import KleinResource
from klein.test.util import TestCase

from .test_resource import LeafResource, requestMock, _render


class PY3KleinResourceTests(TestCase):

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

        d = _render(resource, request)

        self.assertFired(d)
        self.assertEqual(request.getWrittenData(), b"I am a leaf in the wind.")
