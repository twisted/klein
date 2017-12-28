
from twisted.trial.unittest import SynchronousTestCase
from klein import Klein, form, SessionProcurer
from klein._session import requirer # XXX not public because the interface
                                    # needs to be better!
from klein._interfaces import SessionMechanism
from klein.storage.memory import MemorySessionStore
from treq.testing import StubTreq
from treq import content

class TestForms(SynchronousTestCase):
    """
    Tests for L{klein.form} and associated tools.
    """

    def test_handling(self):
        """
        A handler for a form with fields receives those fields as input, as
        passed by an HTTP client.
        """
        calls = []
        mem = MemorySessionStore()
        class TestObject(object):
            router = Klein()
            @requirer
            def authorizor(self):
                return SessionProcurer(mem,
                                       secureTokenHeader=b'X-Test-Session')
            x = form(
                name=form.text(),
                value=form.integer(),
            )
            x = x.authorizedUsing(authorizor)
            @x.handler(router.route("/", methods=['POST']))
            def handler(self, request, name, value):
                calls.append((name, value))
                return b'yay'

        session = self.successResultOf(
            mem.newSession(True, SessionMechanism.Header)
        )

        stub = StubTreq(TestObject().router.resource())
        response = self.successResultOf(stub.post(
            'https://localhost/', data=dict(name='hello', value='1234',
                                            ignoreme='extraneous'),
            headers={b'X-Test-Session': session.identifier}
        ))
        self.assertEqual(response.code, 200)
        self.assertEqual(self.successResultOf(content(response)), b'yay')
        self.assertEqual(calls, [(u'hello', 1234)])
