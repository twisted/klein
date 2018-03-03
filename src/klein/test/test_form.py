from typing import List, TYPE_CHECKING, Text

import attr

from treq import content
from treq.testing import StubTreq

from twisted.trial.unittest import SynchronousTestCase

from klein import Field, Form, Klein, SessionProcurer
from klein._session import requirer
from klein.interfaces import ISessionStore, SessionMechanism
from klein.storage.memory import MemorySessionStore

if TYPE_CHECKING:
    from twisted.web.iweb import IRequest
    IRequest, Text

@attr.s(hash=False)
class TestObject(object):
    sessionStore = attr.ib(type=ISessionStore)
    calls = attr.ib(attr.Factory(list), type=List)

    if TYPE_CHECKING:
        def __init__(self, sessionStore):
            # type: (ISessionStore) -> None
            pass
    router = Klein()

    @requirer
    def authorizor(self):
        # type: () -> SessionProcurer
        return SessionProcurer(self.sessionStore,
                               secureTokenHeader=b'X-Test-Session')
    x = Form(authorizor).withFields(
        name=Field.text(),
        value=Field.integer(),
    )

    @x.handler(router.route("/handle", methods=['POST']))
    def handler(self, request, name, value):
        # type: (IRequest, Text, Text) -> bytes
        self.calls.append((name, value))
        return b'yay'

    @x.renderer(router.route("/render", methods=['GET']),
                action=b'/handle')
    def renderer(self, request, form):
        # type: (IRequest, Form) -> Form
        return form



class TestForms(SynchronousTestCase):
    """
    Tests for L{klein.Form} and associated tools.
    """

    def test_rendering(self):
        # type: () -> None
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
        # type: () -> None
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
