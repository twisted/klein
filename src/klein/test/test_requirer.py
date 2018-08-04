
from typing import TYPE_CHECKING

from treq.testing import StubTreq

from twisted.trial.unittest import SynchronousTestCase
from twisted.web.http_headers import Headers

from klein import Klein, RequestURL, Requirer

if TYPE_CHECKING:               # pragma: no cover
    from typing import Text, Iterable, List, Tuple
    from hyperlink import DecodedURL
    DecodedURL, Text, Iterable, List, Tuple

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
    return url.child("hello/ world").asText()

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
                "https://example.com:8443/hello/world"
            )).text()
        )

        self.assertEqual(
            response,
            "https://example.com:8443/hello/world/hello%2F%20world"
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
