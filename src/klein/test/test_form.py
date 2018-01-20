import attr
from twisted.trial.unittest import SynchronousTestCase
from klein import Klein, Form, SessionProcurer
from klein._session import requirer # XXX not public because the interface
                                    # needs to be better!
from klein._interfaces import SessionMechanism
from klein.storage.memory import MemorySessionStore
from treq.testing import StubTreq
from treq import content

@attr.s(hash=False)
class TestObject(object):
    sessionStore = attr.ib()
    calls = attr.ib(attr.Factory(list))
    router = Klein()
    @requirer
    def authorizor(self):
        return SessionProcurer(self.sessionStore,
                               secureTokenHeader=b'X-Test-Session')
    x = Form(
        name=Form.text(),
        value=Form.integer(),
    )
    x = x.authorizedUsing(authorizor)
    @x.handler(router.route("/handle", methods=['POST']))
    def handler(self, request, name, value):
        self.calls.append((name, value))
        return b'yay'

    @x.renderer(router.route("/render", methods=['GET']),
                action=b'/handle')
    def renderer(self, request, form):
        return form



class TestForms(SynchronousTestCase):
    """
    Tests for L{klein.Form} and associated tools.
    """

    def test_rendering(self):
        """
        Render the given Form.
        """
        mem = MemorySessionStore()

        session = self.successResultOf(
            mem.newSession(True, SessionMechanism.Header)
        )

        stub = StubTreq(TestObject(mem).router.resource())
        response = self.successResultOf(stub.get(
            'https://localhost/render',
            headers={b'X-Test-Session': session.identifier}
        ))
        self.assertEqual(response.code, 200)
        self.assertIn(response.headers.getRawHeaders(b"content-type")[0],
                      b"text/html")


    def test_handling(self):
        """
        A handler for a Form with Fields receives those fields as input, as
        passed by an HTTP client.
        """
        mem = MemorySessionStore()

        session = self.successResultOf(
            mem.newSession(True, SessionMechanism.Header)
        )

        to = TestObject(mem)
        stub = StubTreq(to.router.resource())
        response = self.successResultOf(stub.post(
            'https://localhost/handle',
            data=dict(name='hello', value='1234', ignoreme='extraneous'),
            headers={b'X-Test-Session': session.identifier}
        ))
        self.assertEqual(response.code, 200)
        self.assertEqual(self.successResultOf(content(response)), b'yay')
        self.assertEqual(to.calls, [(u'hello', 1234)])
