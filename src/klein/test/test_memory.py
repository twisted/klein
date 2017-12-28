
from twisted.trial.unittest import SynchronousTestCase
from klein.storage.memory import MemorySessionStore, declareMemoryAuthorizer
from klein.interfaces import ISession, ISessionStore, SessionMechanism
from zope.interface.verify import verifyObject
from zope.interface import Interface


class MemoryTests(SynchronousTestCase):
    """
    Tests for memory-based session storage.
    """

    def test_interfaceCompliance(self):
        """
        Verify that the session store complies with the relevant interfaces.
        """
        store = MemorySessionStore()
        verifyObject(ISessionStore, store)
        verifyObject(
            ISession, self.successResultOf(
                store.newSession(True, SessionMechanism.Header)
            )
        )

    def test_simpleAuthorization(self):
        """
        L{MemorySessionStore.fromAuthorizers} takes a set of functions
        decorated with L{declareMemoryAuthorizer} and constructs a session
        store that can authorize for those interfaces.
        """
        class IFoo(Interface):
            pass
        class IBar(Interface):
            pass

        @declareMemoryAuthorizer(IFoo)
        def fooMe(interface, session, componentized):
            return 1

        @declareMemoryAuthorizer(IBar)
        def barMe(interface, session, componentized):
            return 2

        store = MemorySessionStore.fromAuthorizers([fooMe, barMe])
        session = self.successResultOf(
            store.newSession(False, SessionMechanism.Cookie)
        )
        self.assertEqual(self.successResultOf(session.authorize([IBar, IFoo])),
                         {IFoo: 1, IBar: 2})
