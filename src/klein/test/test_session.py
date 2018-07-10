"""
Tests for L{klein._session}.
"""

from typing import TYPE_CHECKING

from treq.testing import StubTreq

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.trial.unittest import SynchronousTestCase

from klein import Klein, SessionProcurer
from klein.interfaces import ISession, NoSuchSession
from klein.storage.memory import MemorySessionStore

if TYPE_CHECKING:               # pragma: no cover
    from twisted.web.iweb import IRequest
    from twisted.internet.defer import Deferred
    from typing import Tuple, List
    sessions = List[ISession]
    errors = List[NoSuchSession]
    IRequest, Deferred, sessions, errors, Tuple

def simpleSessionRouter():
    # type: () -> Tuple[sessions, errors, str, str, StubTreq]
    """
    Construct a simple router.
    """
    sessions = []
    exceptions = []
    mss = MemorySessionStore()
    router = Klein()
    token = "X-Test-Session-Token"
    cookie = "X-Test-Session-Cookie"
    sproc = SessionProcurer(mss, secureTokenHeader=b"X-Test-Session-Token",
                            secureCookie=b"X-Test-Session-Cookie")

    @router.route("/")
    @inlineCallbacks
    def route(request):
        # type: (IRequest) -> Deferred
        try:
            sessions.append((yield sproc.procureSession(request)))
        except NoSuchSession as nss:
            exceptions.append(nss)
        returnValue(b'ok')

    treq = StubTreq(router.resource())
    return sessions, exceptions, token, cookie, treq

class ProcurementTests(SynchronousTestCase):
    """
    Tests for L{klein.SessionProcurer}.
    """

    def test_procurementSecurity(self):
        # type: () -> None
        """
        Once a session is negotiated, it should be the identical object to
        avoid duplicate work - unless we are using forceInsecure to retrieve
        the insecure session from a secure request, in which case the result
        should not be cached.
        """
        sessions = []
        mss = MemorySessionStore()
        router = Klein()

        @router.route("/")
        @inlineCallbacks
        def route(request):
            # type: (IRequest) -> Deferred
            sproc = SessionProcurer(mss)
            sessions.append(
                (yield sproc.procureSession(request)))
            sessions.append(
                (yield sproc.procureSession(request)))
            sessions.append(
                (yield sproc.procureSession(request, forceInsecure=True)))
            returnValue(b'sessioned')

        treq = StubTreq(router.resource())
        self.successResultOf(treq.get('http://unittest.example.com/'))
        self.assertIs(sessions[0], sessions[1])
        self.assertIs(sessions[0], sessions[2])
        self.successResultOf(treq.get('https://unittest.example.com/'))
        self.assertIs(sessions[3], sessions[4])
        self.assertIsNot(sessions[3], sessions[5])


    def test_unknownSessionHeader(self):
        # type: () -> None
        """
        Unknown session IDs in auth headers will be immediately rejected with
        L{NoSuchSession}.
        """
        sessions, exceptions, token, cookie, treq = simpleSessionRouter()

        response = self.successResultOf(
            treq.get('https://unittest.example.com/', headers={token: u"bad"})
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(len(sessions), 0)
        self.assertEqual(len(exceptions), 1)


    def test_unknownSessionCookieGET(self):
        # type: () -> None
        """
        Unknown session IDs in cookies will result in a new session being
        created.
        """
        badSessionID = "bad"
        sessions, exceptions, token, cookie, treq = simpleSessionRouter()
        response = self.successResultOf(treq.get(
            'https://unittest.example.com/', cookies={cookie: badSessionID}
        ))
        self.assertEqual(response.code, 200)
        self.assertEqual(len(exceptions), 0)
        self.assertEqual(len(sessions), 1)
        self.assertNotEqual(sessions[0].identifier, badSessionID)


    def test_unknownSessionCookiePOST(self):
        # type: () -> None
        """
        Unknown session IDs in cookies for POST requests will result in a
        NoSuchSession error.
        """
        badSessionID = "bad"
        sessions, exceptions, token, cookie, treq = simpleSessionRouter()
        response = self.successResultOf(treq.post(
            'https://unittest.example.com/', cookies={cookie: badSessionID}
        ))
        self.assertEqual(response.code, 200)
        self.assertEqual(len(exceptions), 1)
        self.assertEqual(len(sessions), 0)
