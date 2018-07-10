
import xml.etree.ElementTree as ET
from typing import List, TYPE_CHECKING, Text

import attr

from treq import content
from treq.testing import StubTreq

from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import SynchronousTestCase
from twisted.web.static import Data

from klein import Field, Form, Klein, Requirer, SessionProcurer
from klein.interfaces import (
    EarlyExit, ISession, ISessionStore, NoSuchSession, SessionMechanism
)
from klein.storage.memory import MemorySessionStore

if TYPE_CHECKING:               # pragma: no cover
    from typing import Dict, Tuple, Union
    from twisted.web.iweb import IRequest
    IRequest, Text, Union, Dict, Tuple



def strdict(adict):
    # type: (Dict[Union[bytes, Text], Union[bytes, Text]]) -> Dict[str, str]
    """
    Workaround for a bug in Treq and Twisted where cookie jars cannot
    consistently be text or bytes, but I{must} be native C{str}s on both Python
    versions.

    @type adict: A dictionary which might have bytes or strs or unicodes in it.

    @return: A dictionary with only strs in it.
    """
    strs = {}

    def strify(s):
        # type: (Union[bytes, Text]) -> str
        if isinstance(s, str):
            return s
        elif isinstance(s, bytes):
            return s.decode('utf-8')
        else:
            return s.encode('utf-8')
    for k, v in adict.items():
        strs[strify(k)] = strify(v)
    return strs



class NoSessionResource(Data):
    def render_POST(self, request):
        # type: (IRequest) -> bytes
        request.setResponseCode(403)
        return self.render_GET(request)


@attr.s(hash=False)
class TestObject(object):
    sessionStore = attr.ib(type=ISessionStore)
    calls = attr.ib(attr.Factory(list), type=List)

    router = Klein()
    requirer = Requirer()

    @requirer.prerequisite([ISession])
    @inlineCallbacks
    def procureASession(self, request):
        # type: (IRequest) -> ISession
        try:
            yield (SessionProcurer(self.sessionStore,
                                   secureTokenHeader=b'X-Test-Session')
                   .procureSession(request))
        except NoSuchSession:
            # TODO: this should probably be a bit more frameworky.
            raise EarlyExit(NoSessionResource(b"CSRF failure", "text/plain"))

    @requirer.require(
        router.route("/handle", methods=['POST']),
        name=Field.text(), value=Field.number(),
    )
    def handler(self, request, name, value):
        # type: (IRequest, Text, float) -> bytes
        self.calls.append((name, value))
        return b'yay'

    @requirer.require(
        router.route("/notrequired", methods=['POST']),
        name=Field.text(), value=Field.number(required=False, default=7.0)
    )
    def notRequired(self, request, name, value):
        # type: (IRequest, Text, float) -> bytes
        self.calls.append((name, value))
        return b'okay'

    @requirer.require(
        router.route("/render", methods=['GET']),
        form=Form.rendererFor(handler, action=u'/handle')
    )
    def renderer(self, request, form):
        # type: (IRequest, Form) -> Form
        return form


def simpleFormRouter():
    # type: () -> Tuple[Klein, List[Tuple[str, int]]]
    """
    Create a simple router hooked up to a field handler.
    """
    router = Klein()
    requirer = Requirer()
    calls = []

    @requirer.require(router.route("/getme", methods=['GET']),
                      name=Field.text(), value=Field.number())
    def justGet(request, name, value):
        # type: (IRequest, str, int) -> bytes
        calls.append((name, value))
        return b'got'

    return router, calls

class TestForms(SynchronousTestCase):
    """
    Tests for L{klein.Form} and associated tools.
    """

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


    def test_handlingGET(self):
        # type: () -> None
        """
        A GET handler for a Form with Fields receives query parameters matching
        those field names as input.
        """
        router, calls = simpleFormRouter()

        stub = StubTreq(router.resource())

        response = self.successResultOf(stub.get(
            b"https://localhost/getme?name=hello,%20big+world&value=4321"
        ))
        self.assertEqual(response.code, 200)
        self.assertEqual(self.successResultOf(content(response)), b'got')
        self.assertEqual(calls, [(u'hello, big world', 4321)])


    def test_validatingParameters(self):
        # type: () -> None
        """
        When a parameter fails to validate - for example, a non-number passed
        to a numeric Field, the request fails with a 400 and the default
        validation failure handler displays a form which explains the error.
        """
        router, calls = simpleFormRouter()

        stub = StubTreq(router.resource())

        response = self.successResultOf(stub.get(
            b"https://localhost/getme?"
            b"name=hello,%20big+world&value=not+a+number"
        ))
        responseForm = self.successResultOf(content(response))
        self.assertEqual(response.code, 400)
        self.assertEqual(calls, [])
        responseForm = self.successResultOf(content(response))
        responseDom = ET.fromstring(responseForm)
        errors = responseDom.findall(
            ".//*[@class='klein-form-validation-error']")
        self.assertEqual(len(errors), 1)
        self.assertEquals(errors[0].text, "not a valid number")


    def test_handlingJSON(self):
        # type: () -> None
        """
        A handler for a form with Fields receives those fields as input, as
        passed by an HTTP client that submits a JSON POST body.
        """
        mem = MemorySessionStore()

        session = self.successResultOf(
            mem.newSession(True, SessionMechanism.Header)
        )

        to = TestObject(mem)
        stub = StubTreq(to.router.resource())
        response = self.successResultOf(stub.post(
            'https://localhost/handle',
            json=dict(name='hello', value='1234', ignoreme='extraneous'),
            headers={u'X-Test-Session': session.identifier}
        ))
        self.assertEqual(response.code, 200)
        self.assertEqual(self.successResultOf(content(response)), b'yay')
        self.assertEqual(to.calls, [(u'hello', 1234)])


    def test_missingOptionalParameterJSON(self):
        # type: () -> None
        """
        If a required Field is missing from the JSON body, its default value is
        used.
        """
        mem = MemorySessionStore()

        session = self.successResultOf(
            mem.newSession(True, SessionMechanism.Header)
        )

        to = TestObject(mem)
        stub = StubTreq(to.router.resource())
        response = self.successResultOf(stub.post(
            'https://localhost/notrequired',
            json=dict(name='one'),
            headers={b'X-Test-Session': session.identifier}
        ))
        response2 = self.successResultOf(stub.post(
            'https://localhost/notrequired',
            json=dict(name='two', value=2),
            headers={b'X-Test-Session': session.identifier}
        ))
        self.assertEqual(response.code, 200)
        self.assertEqual(response2.code, 200)
        self.assertEqual(self.successResultOf(content(response)), b'okay')
        self.assertEqual(self.successResultOf(content(response2)), b'okay')
        self.assertEqual(to.calls, [(u'one', 7.0), (u'two', 2.0)])


    def test_rendering(self):
        # type: () -> None
        """
        When a route requires form fields, it renders a form with those fields.
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


    def test_renderingWithNoSessionYet(self):
        # type: () -> None
        """
        When a route is rendered with no session, it sets a cookie to establish
        a new session.
        """
        mem = MemorySessionStore()
        stub = StubTreq(TestObject(mem).router.resource())
        response = self.successResultOf(stub.get('https://localhost/render'))
        self.assertEqual(response.code, 200)
        setCookie = response.cookies()[u'Klein-Secure-Session']
        self.assertIn(
            u'value="{}"'
            .format(setCookie),
            self.successResultOf(content(response)).decode("utf-8")
        )


    def test_noSessionPOST(self):
        # type: () -> None
        """
        An unauthenticated, CSRF-protected form will return a 403 Forbidden
        status code.
        """
        mem = MemorySessionStore()
        to = TestObject(mem)
        stub = StubTreq(to.router.resource())
        response = self.successResultOf(stub.post(
            'https://localhost/handle',
            data=dict(name='hello', value='1234')
        ))
        self.assertEqual(to.calls, [])
        self.assertEqual(response.code, 403)
        self.assertIn(b'CSRF', self.successResultOf(content(response)))


    def test_cookieNoToken(self):
        # type: () -> None
        """
        A cookie-authenticated, CSRF-protected form will return a 403 Forbidden
        status code when a CSRF protection token is not supplied.
        """
        mem = MemorySessionStore()
        session = self.successResultOf(
            mem.newSession(True, SessionMechanism.Cookie)
        )
        to = TestObject(mem)
        stub = StubTreq(to.router.resource())
        response = self.successResultOf(stub.post(
            'https://localhost/handle',
            data=dict(name='hello', value='1234', ignoreme='extraneous'),
            cookies=strdict({"Klein-Secure-Session": session.identifier})
        ))
        self.assertEqual(to.calls, [])
        self.assertEqual(response.code, 403)
        self.assertIn(b'CSRF', self.successResultOf(content(response)))


    def test_cookieWithToken(self):
        # type: () -> None
        """
        A cookie-authenticated, CRSF-protected form will call the form as
        expected.
        """
        mem = MemorySessionStore()
        session = self.successResultOf(
            mem.newSession(True, SessionMechanism.Cookie)
        )
        to = TestObject(mem)
        stub = StubTreq(to.router.resource())
        response = self.successResultOf(stub.post(
            'https://localhost/handle',
            data=dict(name='hello', value='1234', ignoreme='extraneous',
                      __csrf_protection__=session.identifier),
            cookies=strdict({"Klein-Secure-Session": session.identifier})
        ))
        self.assertEqual(to.calls, [('hello', 1234)])
        self.assertEqual(response.code, 200)
        self.assertIn(b'yay', self.successResultOf(content(response)))
