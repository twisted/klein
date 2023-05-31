from typing import Any

from zope.interface import Interface
from zope.interface.verify import verifyObject

from twisted.trial.unittest import SynchronousTestCase

from klein.interfaces import ISession, ISessionStore, SessionMechanism
from klein.storage.memory import MemorySessionStore, declareMemoryAuthorizer


class IFoo(Interface):
    """
    Testing interface 1.
    """


class IBar(Interface):
    """
    Testing interface 2.
    """


class MemoryTests(SynchronousTestCase):
    """
    Tests for memory-based session storage.
    """

    def test_interfaceCompliance(self) -> None:
        """
        Verify that the session store complies with the relevant interfaces.
        """
        store = MemorySessionStore()
        verifyObject(ISessionStore, store)
        verifyObject(
            ISession,
            self.successResultOf(
                store.newSession(True, SessionMechanism.Header)
            ),
        )

    def test_noAuthorizers(self) -> None:
        """
        By default, L{MemorySessionStore} contains no authorizers and the
        sessions it returns will authorize any supplied interfaces as None.
        """
        store = MemorySessionStore()
        session = self.successResultOf(
            store.newSession(True, SessionMechanism.Header)
        )
        self.assertEqual(
            self.successResultOf(session.authorize([IFoo, IBar])), {}
        )

    def test_simpleAuthorization(self) -> None:
        """
        L{MemorySessionStore.fromAuthorizers} takes a set of functions
        decorated with L{declareMemoryAuthorizer} and constructs a session
        store that can authorize for those interfaces.
        """

        @declareMemoryAuthorizer(IFoo)
        def fooMe(interface: Any, session: Any, componentized: Any) -> int:
            return 1

        @declareMemoryAuthorizer(IBar)
        def barMe(interface: Any, session: Any, componentized: Any) -> int:
            return 2

        store = MemorySessionStore.fromAuthorizers([fooMe, barMe])
        session = self.successResultOf(
            store.newSession(False, SessionMechanism.Cookie)
        )
        self.assertEqual(
            self.successResultOf(session.authorize([IBar, IFoo])),
            {IFoo: 1, IBar: 2},
        )
