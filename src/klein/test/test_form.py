from typing import Any, List, Tuple, cast
from xml.etree import ElementTree

import attr
from treq import content
from treq.testing import StubTreq

from twisted.internet.defer import inlineCallbacks
from twisted.python.compat import nativeString
from twisted.trial.unittest import SynchronousTestCase
from twisted.web.iweb import IRequest
from twisted.web.template import Element, TagLoader, renderer, tags

from klein import Field, Form, Klein, RenderableForm, Requirer, SessionProcurer
from klein.interfaces import (
    ISession,
    ISessionStore,
    NoSuchSession,
    SessionMechanism,
    ValidationError,
)
from klein.storage.memory import MemorySessionStore

from .._form import textConverter


class DanglingField(Field):
    """
    A dangling field that, for some reason, doesn't remember its own name when
    told.
    """

    def maybeNamed(self, name: str) -> Field:
        return self


@attr.s(auto_attribs=True, hash=False)
class TestObject:
    sessionStore: ISessionStore
    calls: List = attr.ib(factory=list)

    router = Klein()
    requirer = Requirer()

    @requirer.prerequisite([ISession])
    @inlineCallbacks
    def procureASession(self, request: IRequest) -> Any:
        try:
            yield (
                SessionProcurer(
                    self.sessionStore, secureTokenHeader=b"X-Test-Session"
                ).procureSession(request)
            )
        except NoSuchSession:
            # Intentionally slightly buggy - if a session can't be procured,
            # simply leave it out and rely on checkCSRF to ensure the session
            # component is present before proceeding.
            pass

    @requirer.require(
        router.route("/dangling-param", methods=["POST"]),
        dangling=DanglingField(lambda x: x, "text"),
    )
    def danglingParameter(self, dangling: str) -> None:
        "..."

    @requirer.require(
        router.route("/handle", methods=["POST"]),
        name=Field.text(),
        value=Field.number(),
    )
    def handler(self, name: str, value: float) -> bytes:
        self.calls.append((name, value))
        return b"yay"

    @requirer.require(
        router.route("/handle-submit", methods=["POST"]),
        name=Field.text(),
        button=Field.submit("OK"),
    )
    def handlerWithSubmit(self, name: str, button: str) -> None:
        """
        Form with a submit button.
        """

    @requirer.require(
        router.route("/password-field", methods=["POST"]), pw=Field.password()
    )
    def gotPassword(self, pw: str) -> bytes:
        self.calls.append(("password", pw))
        return b"password received"

    @requirer.require(
        router.route("/notrequired", methods=["POST"]),
        name=Field.text(),
        value=Field.number(required=False, default=7.0),
    )
    def notRequired(self, name: str, value: float) -> bytes:
        self.calls.append((name, value))
        return b"okay"

    @requirer.require(
        router.route("/constrained", methods=["POST"]),
        goldilocks=Field.number(minimum=3, maximum=9),
    )
    def constrained(self, goldilocks: int) -> bytes:
        self.calls.append(("constrained", goldilocks))
        return b"got it"

    @requirer.require(
        router.route("/render", methods=["GET"]),
        form=Form.rendererFor(handler, action="/handle"),
    )
    def renderer(self, form: Form) -> Form:
        return form

    @requirer.require(
        router.route("/render-submit", methods=["GET"]),
        form=Form.rendererFor(handlerWithSubmit, action="/handle-submit"),
    )
    def submitRenderer(self, form: RenderableForm) -> RenderableForm:
        return form

    @requirer.require(
        router.route("/render-custom", methods=["GET"]),
        form=Form.rendererFor(handler, action="/handle"),
    )
    def customFormRender(self, form: RenderableForm) -> Any:
        """
        Include just the glue necessary for CSRF protection and let the
        application render the rest of the form.
        """
        return Element(loader=TagLoader(tags.html(tags.body(form.glue()))))

    @requirer.require(
        router.route("/render-cascade", methods=["GET"]),
        form=Form.rendererFor(handler, action="/handle"),
    )
    def cascadeRenderer(self, form: RenderableForm) -> Element:
        class CustomElement(Element):
            @renderer
            def customize(self, request: IRequest, tag: Any) -> Any:
                return tag("customized")

        form.validationErrors[form._form.fields[0]] = ValidationError(
            message=(tags.div(class_="checkme", render="customize"))
        )

        return CustomElement(loader=TagLoader(form))

    @requirer.require(
        router.route("/handle-validation", methods=["POST"]),
        value=Field.number(maximum=10),
    )
    def customValidation(self, value: int) -> None:
        """
        never called.
        """

    @requirer.require(Form.onValidationFailureFor(customValidation))
    def customFailureHandling(self, values: RenderableForm) -> bytes:
        """
        Handle validation failure.
        """
        self.calls.append(("validation", values))
        return b"~special~"

    @requirer.require(
        router.route("/handle-empty", methods=["POST"]),
    )
    def emptyHandler(self) -> bytes:
        """
        Empty form handler; just for testing rendering.
        """

    @requirer.require(
        router.route("/render-empty", methods=["GET"]),
        form=Form.rendererFor(emptyHandler, action="/handle-empty"),
    )
    def emptyRenderer(self, form: RenderableForm) -> RenderableForm:
        return form


def simpleFormRouter() -> Tuple[Klein, List[Tuple[str, int]]]:
    """
    Create a simple router hooked up to a field handler.
    """
    router = Klein()
    requirer = Requirer()
    calls = []

    @requirer.require(
        router.route("/getme", methods=["GET"]),
        name=Field.text(),
        value=Field.number(),
        custom=Field(formInputType="number", converter=int, required=False),
    )
    def justGet(name: str, value: int, custom: int) -> bytes:
        calls.append((name, value or custom))
        return b"got"

    return router, calls


class TestForms(SynchronousTestCase):
    """
    Tests for L{klein.Form} and associated tools.
    """

    def test_textConverter(self) -> None:
        """
        Convert a string of either type to text.
        """
        text = "f\xf6o"
        for string in (text, text.encode("utf-8")):
            result = textConverter(string)  # type: ignore[type-var]
            self.assertIsInstance(result, str)
            self.assertEqual(result, text)

    def test_handling(self) -> None:
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
        response = self.successResultOf(
            stub.post(
                "https://localhost/handle",
                data=dict(name="hello", value="1234", ignoreme="extraneous"),
                headers={b"X-Test-Session": session.identifier},
            )
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(self.successResultOf(content(response)), b"yay")
        self.assertEqual(to.calls, [("hello", 1234)])

    def test_handlingPassword(self) -> None:
        """
        From the perspective of form handling, passwords are handled like
        strings.
        """
        mem = MemorySessionStore()

        session = self.successResultOf(
            mem.newSession(True, SessionMechanism.Header)
        )

        to = TestObject(mem)
        stub = StubTreq(to.router.resource())
        response = self.successResultOf(
            stub.post(
                "https://localhost/password-field",
                data=dict(pw="asdfjkl;"),
                headers={b"X-Test-Session": session.identifier},
            )
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(
            self.successResultOf(content(response)), b"password received"
        )
        self.assertEqual(to.calls, [("password", "asdfjkl;")])

    def test_numberConstraints(self) -> None:
        """
        Number parameters have minimum and maximum validations and the object
        will not be called when the values exceed them.
        """
        mem = MemorySessionStore()

        session = self.successResultOf(
            mem.newSession(True, SessionMechanism.Header)
        )

        to = TestObject(mem)
        stub = StubTreq(to.router.resource())
        tooLow = self.successResultOf(
            stub.post(
                "https://localhost/constrained",
                data=dict(goldilocks="1"),
                headers={b"X-Test-Session": session.identifier},
            )
        )
        tooHigh = self.successResultOf(
            stub.post(
                "https://localhost/constrained",
                data=dict(goldilocks="20"),
                headers={b"X-Test-Session": session.identifier},
            )
        )
        justRight = self.successResultOf(
            stub.post(
                "https://localhost/constrained",
                data=dict(goldilocks="7"),
                headers={b"X-Test-Session": session.identifier},
            )
        )

        self.assertEqual(tooHigh.code, 400)
        self.assertEqual(tooLow.code, 400)
        self.assertEqual(justRight.code, 200)
        self.assertEqual(self.successResultOf(content(justRight)), b"got it")
        self.assertEqual(to.calls, [("constrained", 7)])

    def test_missingRequiredParameter(self) -> None:
        """
        If required fields are missing, a default error form is presented and
        the form's handler is not called.
        """
        mem = MemorySessionStore()

        session = self.successResultOf(
            mem.newSession(True, SessionMechanism.Header)
        )

        to = TestObject(mem)
        stub = StubTreq(to.router.resource())
        response = self.successResultOf(
            stub.post(
                "https://localhost/handle",
                data=dict(),
                headers={b"X-Test-Session": session.identifier},
            )
        )
        self.assertEqual(response.code, 400)
        self.assertIn(
            b"a value was required but none was supplied",
            self.successResultOf(content(response)),
        )
        self.assertEqual(to.calls, [])

    def test_noName(self) -> None:
        """
        A handler for a Form with a Field that doesn't have a name will return
        an error explaining the problem.
        """
        mem = MemorySessionStore()
        session = self.successResultOf(
            mem.newSession(True, SessionMechanism.Header)
        )
        to = TestObject(mem)
        stub = StubTreq(to.router.resource())
        response = self.successResultOf(
            stub.post(
                "https://localhost/dangling-param",
                data=dict(),
                headers={b"X-Test-Session": session.identifier},
            )
        )
        self.assertEqual(response.code, 500)
        errors = self.flushLoggedErrors(ValueError)
        self.assertEqual(len(errors), 1)
        self.assertIn(
            str(errors[0].value), "Cannot extract unnamed form field."
        )

    def test_handlingGET(self) -> None:
        """
        A GET handler for a Form with Fields receives query parameters matching
        those field names as input.
        """
        router, calls = simpleFormRouter()

        stub = StubTreq(router.resource())

        response = self.successResultOf(
            stub.get(
                b"https://localhost/getme?name=hello,%20big+world&value=4321"
            )
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(self.successResultOf(content(response)), b"got")
        self.assertEqual(calls, [("hello, big world", 4321)])

    def test_validatingParameters(self) -> None:
        """
        When a parameter fails to validate - for example, a non-number passed
        to a numeric Field, the request fails with a 400 and the default
        validation failure handler displays a form which explains the error.
        """
        router, calls = simpleFormRouter()

        stub = StubTreq(router.resource())

        response = self.successResultOf(
            stub.get(
                b"https://localhost/getme?"
                b"name=hello,%20big+world&value=not+a+number"
            )
        )
        responseForm = self.successResultOf(content(response))
        self.assertEqual(response.code, 400)
        self.assertEqual(calls, [])
        responseForm = self.successResultOf(content(response))
        responseDom = ElementTree.fromstring(responseForm)
        errors = responseDom.findall(
            ".//*[@class='klein-form-validation-error']"
        )
        self.assertEqual(len(errors), 1)
        self.assertEquals(errors[0].text, "not a valid number")

    def test_customParameterValidation(self) -> None:
        """
        When a custom parameter fails to validate by raising ValueError - for
        example, a non-number passed to a numeric Field, the request fails with
        a 400 and the default validation failure handler displays a form which
        explains the error.
        """
        router, calls = simpleFormRouter()

        stub = StubTreq(router.resource())

        response = self.successResultOf(
            stub.get(
                b"https://localhost/getme?"
                b"name=hello,%20big+world&value=0&custom=not+a+number"
            )
        )
        responseForm = self.successResultOf(content(response))
        self.assertEqual(response.code, 400)
        self.assertEqual(calls, [])
        responseForm = self.successResultOf(content(response))
        responseDom = ElementTree.fromstring(responseForm)
        errors = responseDom.findall(
            ".//*[@class='klein-form-validation-error']"
        )
        self.assertEqual(len(errors), 1)
        errorText = cast(str, errors[0].text)
        self.assertIsNot(errorText, None)
        self.assertEqual(
            errorText,
            "invalid literal for int() with base 10: 'not a number'",
        )

    def test_handlingJSON(self) -> None:
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
        response = self.successResultOf(
            stub.post(
                "https://localhost/handle",
                json=dict(name="hello", value="1234", ignoreme="extraneous"),
                headers={"X-Test-Session": session.identifier},
            )
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(self.successResultOf(content(response)), b"yay")
        self.assertEqual(to.calls, [("hello", 1234)])

    def test_missingOptionalParameterJSON(self) -> None:
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
        response = self.successResultOf(
            stub.post(
                "https://localhost/notrequired",
                json=dict(name="one"),
                headers={b"X-Test-Session": session.identifier},
            )
        )
        response2 = self.successResultOf(
            stub.post(
                "https://localhost/notrequired",
                json=dict(name="two", value=2),
                headers={b"X-Test-Session": session.identifier},
            )
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(response2.code, 200)
        self.assertEqual(self.successResultOf(content(response)), b"okay")
        self.assertEqual(self.successResultOf(content(response2)), b"okay")
        self.assertEqual(to.calls, [("one", 7.0), ("two", 2.0)])

    def test_rendering(self) -> None:
        """
        When a route requires form fields, it renders a form with those fields.
        """
        mem = MemorySessionStore()

        session = self.successResultOf(
            mem.newSession(True, SessionMechanism.Header)
        )

        stub = StubTreq(TestObject(mem).router.resource())
        response = self.successResultOf(
            stub.get(
                "https://localhost/render",
                headers={b"X-Test-Session": session.identifier},
            )
        )
        self.assertEqual(response.code, 200)
        self.assertIn(
            response.headers.getRawHeaders(b"content-type")[0], b"text/html"
        )
        responseDom = ElementTree.fromstring(
            self.successResultOf(content(response))
        )
        submitButton = responseDom.findall(".//*[@type='submit']")
        self.assertEqual(len(submitButton), 1)
        self.assertEqual(
            submitButton[0].attrib["name"], "__klein_auto_submit__"
        )

    def test_renderingExplicitSubmit(self) -> None:
        """
        When a form renderer specifies a submit button, no automatic submit
        button is rendered.
        """
        mem = MemorySessionStore()

        session = self.successResultOf(
            mem.newSession(True, SessionMechanism.Header)
        )

        stub = StubTreq(TestObject(mem).router.resource())
        response = self.successResultOf(
            stub.get(
                "https://localhost/render-submit",
                headers={b"X-Test-Session": session.identifier},
            )
        )
        self.assertEqual(response.code, 200)
        self.assertIn(
            response.headers.getRawHeaders(b"content-type")[0], b"text/html"
        )
        responseDom = ElementTree.fromstring(
            self.successResultOf(content(response))
        )
        submitButton = responseDom.findall(".//*[@type='submit']")
        self.assertEqual(len(submitButton), 1)
        self.assertEqual(submitButton[0].attrib["name"], "button")

    def test_renderingFormGlue(self) -> None:
        """
        When a form renderer renders just the glue, none of the rest of the
        form is included.
        """
        mem = MemorySessionStore()

        session = self.successResultOf(
            mem.newSession(True, SessionMechanism.Header)
        )

        stub = StubTreq(TestObject(mem).router.resource())
        response = self.successResultOf(
            stub.get(
                "https://localhost/render-custom",
                headers={b"X-Test-Session": session.identifier},
            )
        )
        self.assertEqual(response.code, 200)
        self.assertIn(
            response.headers.getRawHeaders(b"content-type")[0], b"text/html"
        )
        responseDom = ElementTree.fromstring(
            self.successResultOf(content(response))
        )
        submitButton = responseDom.findall(".//*[@type='submit']")
        self.assertEqual(len(submitButton), 0)
        protectionField = responseDom.findall(
            ".//*[@name='__csrf_protection__']"
        )
        self.assertEqual(protectionField[0].attrib["value"], session.identifier)

    def test_renderingEmptyForm(self) -> None:
        """
        When a form renderer specifies a submit button, no automatic submit
        button is rendered.
        """
        mem = MemorySessionStore()

        session = self.successResultOf(
            mem.newSession(True, SessionMechanism.Header)
        )

        stub = StubTreq(TestObject(mem).router.resource())
        response = self.successResultOf(
            stub.get(
                "https://localhost/render-empty",
                headers={b"X-Test-Session": session.identifier},
            )
        )
        self.assertEqual(response.code, 200)
        self.assertIn(
            response.headers.getRawHeaders(b"content-type")[0], b"text/html"
        )
        responseDom = ElementTree.fromstring(
            self.successResultOf(content(response))
        )
        submitButton = responseDom.findall(".//*[@type='submit']")
        self.assertEqual(len(submitButton), 1)
        self.assertEqual(
            submitButton[0].attrib["name"], "__klein_auto_submit__"
        )
        protectionField = responseDom.findall(
            ".//*[@name='__csrf_protection__']"
        )
        self.assertEqual(protectionField[0].attrib["value"], session.identifier)

    def test_renderLookupError(self) -> None:
        """
        RenderableForm raises L{MissingRenderMethod} if anything attempts to
        look up a render method on it.
        """
        mem = MemorySessionStore()

        session = self.successResultOf(
            mem.newSession(True, SessionMechanism.Header)
        )

        stub = StubTreq(TestObject(mem).router.resource())
        response = self.successResultOf(
            stub.get(
                "https://localhost/render-cascade",
                headers={b"X-Test-Session": session.identifier},
            )
        )
        self.assertEqual(response.code, 200)
        # print(self.successResultOf(response.content()).decode('utf-8'))
        failures = self.flushLoggedErrors()
        self.assertEqual(len(failures), 1)
        self.assertIn("MissingRenderMethod", str(failures[0]))

    def test_customValidationHandling(self) -> None:
        """
        L{Form.onValidationFailureFor} handles form validation failures by
        handing its thing a renderable form.
        """
        mem = MemorySessionStore()

        session = self.successResultOf(
            mem.newSession(True, SessionMechanism.Header)
        )

        testobj = TestObject(mem)
        stub = StubTreq(testobj.router.resource())
        response = self.successResultOf(
            stub.post(
                "https://localhost/handle-validation",
                headers={b"X-Test-Session": session.identifier},
                json={"value": 300},
            )
        )
        self.assertEqual(response.code, 200)
        self.assertIn(
            response.headers.getRawHeaders(b"content-type")[0], b"text/html"
        )
        responseText = self.successResultOf(content(response))
        self.assertEqual(responseText, b"~special~")
        self.assertEqual(
            [
                (k.pythonArgumentName, v)
                for k, v in testobj.calls[-1][1].prevalidationValues.items()
            ],
            [("value", 300)],
        )

    def test_renderingWithNoSessionYet(self) -> None:
        """
        When a route is rendered with no session, it sets a cookie to establish
        a new session.
        """
        mem = MemorySessionStore()
        stub = StubTreq(TestObject(mem).router.resource())
        response = self.successResultOf(stub.get("https://localhost/render"))
        self.assertEqual(response.code, 200)
        setCookie = response.cookies()["Klein-Secure-Session"]
        expected = f'value="{setCookie}"'
        actual = self.successResultOf(content(response)).decode("utf-8")
        self.assertIn(expected, actual)

    def test_noSessionPOST(self) -> None:
        """
        An unauthenticated, CSRF-protected form will return a 403 Forbidden
        status code.
        """
        mem = MemorySessionStore()
        to = TestObject(mem)
        stub = StubTreq(to.router.resource())
        response = self.successResultOf(
            stub.post(
                "https://localhost/handle",
                data=dict(name="hello", value="1234"),
            )
        )
        self.assertEqual(to.calls, [])
        self.assertEqual(response.code, 403)
        self.assertIn(b"CSRF", self.successResultOf(content(response)))

    def test_cookieNoToken(self) -> None:
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
        response = self.successResultOf(
            stub.post(
                "https://localhost/handle",
                data=dict(name="hello", value="1234", ignoreme="extraneous"),
                cookies={
                    "Klein-Secure-Session": nativeString(session.identifier)
                },
            )
        )
        self.assertEqual(to.calls, [])
        self.assertEqual(response.code, 403)
        self.assertIn(b"CSRF", self.successResultOf(content(response)))

    def test_cookieWithToken(self) -> None:
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
        response = self.successResultOf(
            stub.post(
                "https://localhost/handle",
                data=dict(
                    name="hello",
                    value="1234",
                    ignoreme="extraneous",
                    __csrf_protection__=session.identifier,
                ),
                cookies={
                    "Klein-Secure-Session": nativeString(session.identifier)
                },
            )
        )
        self.assertEqual(to.calls, [("hello", 1234)])
        self.assertEqual(response.code, 200)
        self.assertIn(b"yay", self.successResultOf(content(response)))
