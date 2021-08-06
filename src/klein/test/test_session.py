"""
Tests for L{klein._session}.
"""

from typing import Any, Generator, List, Tuple, Type

from treq.testing import StubTreq
from zope.interface import Interface, implementer

from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.python.components import Componentized
from twisted.trial.unittest import SynchronousTestCase
from twisted.web.iweb import IRequest

from klein import Authorization, Klein, Requirer, SessionProcurer
from klein.interfaces import ISession, NoSuchSession, TooLateForCookies
from klein.storage.memory import MemorySessionStore, declareMemoryAuthorizer


Sessions = List[ISession]
Errors = List[NoSuchSession]


class ISimpleTest(Interface):
    """
    Interface for testing.
    """

    def doTest() -> int:
        """
        Test method.
        """


class IDenyMe(Interface):
    """
    Interface that is never provided.
    """


@implementer(ISimpleTest)
class SimpleTest:
    """
    Implementation of L{ISimpleTest} for testing.
    """

    def doTest(self) -> int:
        """
        Implementation of L{ISimpleTest}.  Returns 3.
        """
        return 3


@declareMemoryAuthorizer(ISimpleTest)
def memoryAuthorizer(
    interface: Type[Interface], session: ISession, data: Componentized
) -> SimpleTest:
    """
    Authorize the ISimpleTest interface; it always works.
    """
    return SimpleTest()


def simpleSessionRouter() -> Tuple[Sessions, Errors, str, str, StubTreq]:
    """
    Construct a simple router.
    """
    sessions: Sessions = []
    exceptions: Errors = []
    mss = MemorySessionStore.fromAuthorizers([memoryAuthorizer])
    router = Klein()
    token = "X-Test-Session-Token"
    cookie = "X-Test-Session-Cookie"
    sproc = SessionProcurer(
        mss,
        secureTokenHeader=b"X-Test-Session-Token",
        secureCookie=b"X-Test-Session-Cookie",
    )

    @router.route("/")
    @inlineCallbacks
    def route(request: IRequest) -> Generator[Any, object, bytes]:
        try:
            sessions.append(
                (yield sproc.procureSession(request)),  # type: ignore[arg-type]
            )
        except NoSuchSession as nss:
            exceptions.append(nss)
        return b"ok"

    requirer = Requirer()

    @requirer.prerequisite([ISession])
    def procure(request: IRequest) -> Deferred:
        return sproc.procureSession(request)

    @requirer.require(router.route("/test"), simple=Authorization(ISimpleTest))
    def testRoute(simple: SimpleTest) -> str:
        return "ok: " + str(simple.doTest() + 4)

    @requirer.require(router.route("/denied"), nope=Authorization(IDenyMe))
    def testDenied(nope: IDenyMe) -> str:
        return "bad"

    treq = StubTreq(router.resource())
    return sessions, exceptions, token, cookie, treq


class ProcurementTests(SynchronousTestCase):
    """
    Tests for L{klein.SessionProcurer}.
    """

    def test_procurementSecurity(self) -> None:
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
        def route(request: IRequest) -> Generator[Any, object, bytes]:
            sproc = SessionProcurer(mss)
            sessions.append((yield sproc.procureSession(request)))
            sessions.append((yield sproc.procureSession(request)))
            sessions.append(
                (yield sproc.procureSession(request, forceInsecure=True))
            )
            return b"sessioned"

        treq = StubTreq(router.resource())
        self.successResultOf(treq.get("http://unittest.example.com/"))
        self.assertIs(sessions[0], sessions[1])
        self.assertIs(sessions[0], sessions[2])
        self.successResultOf(treq.get("https://unittest.example.com/"))
        self.assertIs(sessions[3], sessions[4])
        self.assertIsNot(sessions[3], sessions[5])

    def test_procuredTooLate(self) -> None:
        """
        If you start writing stuff to the response before procuring the
        session, when cookies need to be set, you will get a comprehensible
        error.
        """
        mss = MemorySessionStore()
        router = Klein()

        @router.route("/")  # type: ignore[arg-type]
        @inlineCallbacks
        def route(request: IRequest) -> Generator[Any, object, None]:
            sproc = SessionProcurer(mss)
            request.write(b"oops...")
            with self.assertRaises(TooLateForCookies):
                yield sproc.procureSession(request)
            request.write(b"bye")
            request.finish()

        treq = StubTreq(router.resource())
        result = self.successResultOf(treq.get("http://unittest.example.com/"))
        self.assertEqual(self.successResultOf(result.content()), b"oops...bye")

    def test_cookiesTurnedOff(self) -> None:
        """
        If cookies can't be set, then C{procureSession} raises
        L{NoSuchSession}.
        """
        mss = MemorySessionStore()
        router = Klein()

        @router.route("/")
        @inlineCallbacks
        def route(request: IRequest) -> Generator[Any, object, bytes]:
            sproc = SessionProcurer(mss, setCookieOnGET=False)
            with self.assertRaises(NoSuchSession):
                yield sproc.procureSession(request)
            return b"no session"

        treq = StubTreq(router.resource())
        result = self.successResultOf(treq.get("http://unittest.example.com/"))
        self.assertEqual(self.successResultOf(result.content()), b"no session")

    def test_unknownSessionHeader(self) -> None:
        """
        Unknown session IDs in auth headers will be immediately rejected with
        L{NoSuchSession}.
        """
        sessions, exceptions, token, cookie, treq = simpleSessionRouter()

        response = self.successResultOf(
            treq.get("https://unittest.example.com/", headers={token: "bad"})
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(len(sessions), 0)
        self.assertEqual(len(exceptions), 1)

    def test_unknownSessionCookieGET(self) -> None:
        """
        Unknown session IDs in cookies will result in a new session being
        created.
        """
        badSessionID = "bad"
        sessions, exceptions, token, cookie, treq = simpleSessionRouter()
        response = self.successResultOf(
            treq.get(
                "https://unittest.example.com/", cookies={cookie: badSessionID}
            )
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(len(exceptions), 0)
        self.assertEqual(len(sessions), 1)
        self.assertNotEqual(sessions[0].identifier, badSessionID)

    def test_unknownSessionCookiePOST(self) -> None:
        """
        Unknown session IDs in cookies for POST requests will result in a
        NoSuchSession error.
        """
        badSessionID = "bad"
        sessions, exceptions, token, cookie, treq = simpleSessionRouter()
        response = self.successResultOf(
            treq.post(
                "https://unittest.example.com/", cookies={cookie: badSessionID}
            )
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(len(exceptions), 1)
        self.assertEqual(len(sessions), 0)

    def test_authorization(self) -> None:
        """
        When L{Requirer.require} is used with L{Authorization} and the session
        knows how to supply that authorization, it is passed to the object.
        """
        sessions, exceptions, token, cookie, treq = simpleSessionRouter()
        response = self.successResultOf(
            treq.get("https://unittest.example.com/test")
        )
        self.assertEqual(self.successResultOf(response.content()), b"ok: 7")

    def test_authorizationDenied(self) -> None:
        """
        When L{Requirer.require} is used with an L{Authorization} and the
        session does I{not} know how to supply that authorization, the callable
        is not invoked.
        """
        sessions, exceptions, token, cookie, treq = simpleSessionRouter()
        response = self.successResultOf(
            treq.get("https://unittest.example.com/denied")
        )
        self.assertEqual(
            self.successResultOf(response.content()),
            b"klein.test.test_session.IDenyMe DENIED",
        )
