
from treq.testing import StubTreq

from twisted.trial.unittest import SynchronousTestCase

from typing import TYPE_CHECKING

from klein import Klein, RequestURL, Requirer

if TYPE_CHECKING:               # pragma: no cover
    from typing import Text
    from hyperlink import DecodedURL
    DecodedURL, Text


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
                "https://asdf.com/hello/world"
            )).text()
        )

        self.assertEqual(response,
                         "https://asdf.com/hello/world/hello%2F%20world")
