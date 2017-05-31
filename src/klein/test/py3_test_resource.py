import twisted

from klein import Klein
from klein.resource import KleinResource
from klein.test.util import TestCase

from .test_resource import LeafResource, _render, requestMock


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

        if (twisted.version.major, twisted.version.minor) >= (16, 6):
            expected = b"I am a leaf in the wind."

            d = _render(resource, request)

        else:
            expected = b"** Twisted>=16.6 is required **"

            # Twisted version in use does not have ensureDeferred, so
            # attempting to use an async resource will raise
            # NotImplementedError.
            # resource.render(), and therefore _render(), does not return the
            # deferred object that does the rendering, so we need to check for
            # errors indirectly via handle_errors().
            @app.handle_errors(NotImplementedError)
            def notImplementedError(request, failure):
                return expected

            d = _render(resource, request)

        def assertResult(_):
            self.assertEqual(request.getWrittenData(), expected)

        d.addCallback(assertResult)

        return d
