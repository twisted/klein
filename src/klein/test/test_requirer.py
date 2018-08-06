
from typing import TYPE_CHECKING

from treq.testing import StubTreq

from twisted.trial.unittest import SynchronousTestCase
from twisted.web.http_headers import Headers

from zope.interface import Interface

from klein import Klein, RequestComponent, RequestURL, Requirer, Response

if TYPE_CHECKING:               # pragma: no cover
    from typing import Text, Iterable, List, Tuple
    from hyperlink import DecodedURL
    from twisted.web.iweb import IRequest
    DecodedURL, Text, Iterable, List, Tuple, IRequest

class BadlyBehavedHeaders(Headers):
    """
    Make L{Headers} lie, and refuse to return a Host header from
    getAllRequestHeaders.
    """

    def getAllRawHeaders(self):
        # type: () -> Iterable[Tuple[bytes, List[bytes]]]
        """
        Don't return a host header.
        """
        for key, values in super(BadlyBehavedHeaders, self).getAllRawHeaders():
            if key != b'Host':
                yield (key, values)


router = Klein()
requirer = Requirer()
@requirer.require(router.route("/hello/world", methods=['GET']),
                  url=RequestURL())
def requiresURL(url):
    # type: (DecodedURL) -> Text
    """
    This is a route that requires a URL.
    """
    return url.child(u"hello/ world").asText()

class ISample(Interface):
    """
    Interface for testing.
    """

@requirer.prerequisite([ISample])
def provideSample(request):
    # type: (IRequest) -> None
    """
    This requirer prerequisite installs a string as the provider of ISample.
    """
    request.setComponent(ISample, "sample component")

@requirer.require(router.route("/retrieve/component", methods=['GET']),
                  component=RequestComponent(ISample))
def needsComponent(component):
    # type: (Text) -> Text
    """
    This route requires and returns an L{ISample}.
    """
    return component

@requirer.require(router.route("/set/headers"))
def someHeaders():
    # type: () -> Response
    """
    Set some response attributes.
    """
    return Response(
        209, {'x-single-header': b'one',
              'x-multi-header': [b'two', b'three']},
        "this is the response body"
    )


class RequireURLTests(SynchronousTestCase):
    """
    Tests for RequestURL() required parameter.
    """

    def test_requiresURL(self):
        # type: () -> None
        """
        When RequestURL is specified to a requirer, a DecodedURL object will be
        passed in to the decorated route.
        """
        response = self.successResultOf(
            self.successResultOf(StubTreq(router.resource()).get(
                "https://example.com/hello/world"
            )).text()
        )

        self.assertEqual(response,
                         "https://example.com/hello/world/hello%2F%20world")

    def test_requiresURLNonStandardPort(self):
        # type: () -> None
        """
        When RequestURL is specified to a requirer, a DecodedURL object will be
        passed in to the decorated route.
        """
        response = self.successResultOf(
            self.successResultOf(StubTreq(router.resource()).get(
                "http://example.com:8080/hello/world"
            )).text()
        )

        self.assertEqual(
            response,
            "http://example.com:8080/hello/world/hello%2F%20world"
        )

    def test_requiresURLBadlyBehavedClient(self):
        # type: () -> None
        """
        requiresURL will press on in the face of badly-behaved client code.
        """
        response = self.successResultOf(
            self.successResultOf(StubTreq(router.resource()).get(
                "https://example.com/hello/world",
                headers=BadlyBehavedHeaders()
            )).text()
        )
        self.assertEqual(
            response,
            # Static values from StubTreq - this should probably be tunable.
            "https://127.0.0.1:31337/hello/world/hello%2F%20world"
        )

class RequireComponentTests(SynchronousTestCase):
    """
    Tests for RequestComponent.
    """

    def test_requestComponent(self):
        # type: () -> None
        """
        Test for requiring a component installed on the request.
        """
        response = self.successResultOf(
            self.successResultOf(StubTreq(router.resource()).get(
                "https://example.com/retrieve/component",
            )).text()
        )
        self.assertEqual(
            response, "sample component"
        )


class ResponseTests(SynchronousTestCase):
    """
    Tests for L{klein.Response}.
    """

    def test_basicResponse(self):
        # type: () -> None
        """
        Since methods decorated with C{@require} don't receive the request and
        can't access it to set headers and response codes, instead, they can
        return a Response object that has those attributes.
        """
        response = self.successResultOf(StubTreq(router.resource()).get(
            "https://example.com/set/headers",
        ))
        self.assertEqual(response.code, 209)
        self.assertEqual(response.headers.getRawHeaders(b"X-Single-Header"),
                         [b'one'])
        self.assertEqual(response.headers.getRawHeaders(b"X-Multi-Header"),
                         [b'two', b'three'])
