"""
Tests for L{klein._session}.
"""

from typing import TYPE_CHECKING

from treq.testing import StubTreq

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.trial.unittest import SynchronousTestCase

from klein import Klein, SessionProcurer
from klein.storage.memory import MemorySessionStore

if TYPE_CHECKING:               # pragma: no cover
    from twisted.web.iweb import IRequest
    from twisted.internet.defer import Deferred
    IRequest, Deferred

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
