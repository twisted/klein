# -*- test-case-name: klein.test.test_form -*-

import json
from typing import (
    Any,
    AnyStr,
    Callable,
    Dict,
    Generator,
    Iterable,
    List,
    NoReturn,
    Optional,
    Sequence,
    Type,
    cast,
)

import attr
from zope.interface import Attribute, Interface, implementer

from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.python.components import Componentized, registerAdapter
from twisted.web.error import MissingRenderMethod
from twisted.web.http import FORBIDDEN
from twisted.web.iweb import IRenderable, IRequest
from twisted.web.resource import Resource
from twisted.web.template import Element, Tag, TagLoader, tags

from ._app import KleinRenderable, _call
from ._decorators import bindable
from .interfaces import (
    EarlyExit,
    IDependencyInjector,
    IRequestLifecycle,
    IRequiredParameter,
    ISession,
    SessionMechanism,
    ValidationError,
    ValueAbsent,
)


class CrossSiteRequestForgery(Resource):
    """
    Cross site request forgery detected.  Request aborted.
    """

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def render(self, request: IRequest) -> bytes:
        """
        For all HTTP methods, return a 403.
        """
        request.setResponseCode(FORBIDDEN, b"FAILURECSRF")
        return ("CSRF TOKEN FAILURE: " + self.message).encode("utf-8")


CSRF_PROTECTION = "__csrf_protection__"


def textConverter(value: AnyStr) -> str:
    """
    Converter for form values (which may be any type of string) into text.
    """
    if isinstance(value, bytes):
        return value.decode("utf-8")
    else:
        return value


class IParsedJSONBody(Interface):
    """
    Marker interface for the dict parsed from the request body's JSON contents.
    """

    # TODO: how to allow applications to pass options to loads, such as
    # parse_float?


@implementer(IRequiredParameter)
@attr.s(auto_attribs=True, frozen=True)
class Field:
    """
    A L{Field} is a static part of a L{Form}.

    @ivar converter: The converter.
    """

    converter: Callable[[AnyStr], Any]
    formInputType: str
    pythonArgumentName: Optional[str] = None
    formFieldName: Optional[str] = None
    formLabel: Optional[str] = None
    default: Optional[Any] = attr.ib(default=None, cmp=False)
    required: bool = True
    noLabel: bool = False
    value: str = ""
    error: Optional[ValidationError] = None

    # IRequiredParameter
    def registerInjector(
        self,
        injectionComponents: Componentized,
        parameterName: str,
        requestLifecycle: IRequestLifecycle,
    ) -> IDependencyInjector:
        """
        Register this form field as a dependency injector.
        """
        protoForm = IProtoForm(injectionComponents)
        return cast(
            IDependencyInjector,
            protoForm.addField(self.maybeNamed(parameterName)),
        )

    def maybeNamed(self, name: str) -> "Field":
        """
        Create a new L{Field} like this one, but with all the name default
        values filled in.

        @param name: the name.
        """

        def maybe(
            it: Optional[str], that: Optional[str] = name
        ) -> Optional[str]:
            return that if it is None else it

        return attr.assoc(
            self,
            pythonArgumentName=maybe(self.pythonArgumentName),
            formFieldName=maybe(self.formFieldName),
            formLabel=maybe(
                self.formLabel, name.capitalize() if not self.noLabel else None
            ),
        )

    def asTags(self) -> Iterable[Tag]:
        """
        Convert this L{Field} into some stuff that can be rendered in a
        L{twisted.web.template}.

        @return: A new set of tags to include in a template.
        """
        value = self.value
        if value is None:
            value = ""  # type: ignore[unreachable]
        input_tag = tags.input(
            type=self.formInputType,
            name=self.formFieldName,  # type: ignore[arg-type]
            value=value,
        )
        error_tags = []
        if self.error:
            error_tags.append(
                tags.div(class_="klein-form-validation-error")(
                    self.error.message  # type: ignore[arg-type]
                )
            )
        if self.formLabel:
            yield tags.label(self.formLabel, ": ", input_tag, *error_tags)
        else:
            yield input_tag
            yield from error_tags

    def extractValue(self, request: IRequest) -> Any:
        """
        Extract a value from the request.

        In the case of key/value form posts, this attempts to reliably make the
        value into str.  In the case of a JSON post, however, it will simply
        extract the value from the top-level dictionary, which means it could
        be any arrangement of JSON-serializiable objects.
        """
        fieldName = self.formFieldName
        if fieldName is None:
            raise ValueError("Cannot extract unnamed form field.")
        contentType = request.getHeader(b"content-type")
        if contentType is not None and contentType.startswith(
            b"application/json"
        ):
            # TODO: parse only once, please.
            parsed = cast(Componentized, request).getComponent(IParsedJSONBody)
            if parsed is None:
                request.content.seek(0)
                octets = request.content.read()
                characters = octets.decode("utf-8")
                parsed = json.loads(characters)
                cast(Componentized, request).setComponent(
                    IParsedJSONBody, parsed
                )
            if fieldName not in parsed:
                return None
            return parsed[fieldName]
        allValues = request.args.get(fieldName.encode("utf-8"))
        if allValues:
            return allValues[0].decode("utf-8")
        else:
            return None

    def validateValue(self, value: Any) -> Any:
        """
        Validate the given text and return a converted Python object to use, or
        fail with L{ValidationError}.

        @param value: The value that was extracted by L{Field.extractValue}.

        @return: The converted value.
        """
        if value is None:
            if self.required:
                raise ValueAbsent("a value was required but none was supplied")
            else:
                return self.default
        try:
            return self.converter(value)
        except ValueError as ve:
            raise ValidationError(str(ve))

    @classmethod
    def text(cls, **kw: Any) -> "Field":
        """
        Shorthand for a form field that contains a short string, and will be
        rendered as a plain <input>.
        """
        return cls(converter=textConverter, formInputType="text", **kw)

    @classmethod
    def password(cls, **kw: Any) -> "Field":
        """
        Shorthand for a form field that, like L{text}, contains a short string,
        but should be obscured when typed (and, to the extent possible,
        obscured in other sensitive contexts, such as logging.)
        """
        return cls(converter=textConverter, formInputType="password", **kw)

    @classmethod
    def hidden(cls, name: str, value: str, **kw: Any) -> "Field":
        """
        Shorthand for a hidden field.
        """
        return cls(
            converter=textConverter,
            formInputType="hidden",
            noLabel=True,
            value=value,
            **kw,
        ).maybeNamed(name)

    @classmethod
    def number(
        cls,
        minimum: Optional[int] = None,
        maximum: Optional[int] = None,
        kind: Type = float,
        **kw: Any,
    ) -> "Field":
        """
        An integer within the range [minimum, maximum].
        """

        def bounded_number(text: AnyStr) -> Any:
            try:
                value = kind(text)
            except (ValueError, ArithmeticError):
                raise ValidationError("not a valid number")
            else:
                if minimum is not None and value < minimum:
                    raise ValidationError("value must be >=" + repr(minimum))
                if maximum is not None and value > maximum:
                    raise ValidationError("value must be <=" + repr(maximum))
                return value

        return cls(converter=bounded_number, formInputType="number", **kw)

    @classmethod
    def submit(cls, value: str) -> "Field":
        """
        A field representing a submit button, with a value (displayed on the
        button).
        """
        return cls(
            converter=textConverter,
            formInputType="submit",
            noLabel=True,
            default=value,
        )


@implementer(IRenderable)
@attr.s(auto_attribs=True)
class RenderableForm:
    """
    An L{IRenderable} representing a renderable form.

    @ivar prevalidationValues: a L{dict} mapping {L{Field}: L{list} of
        L{str}}, representing the value that each field received as part of
        the request.

    @ivar validationErrors: a L{dict} mapping {L{Field}: L{ValidationError}}
    """

    _form: "IForm"
    _session: ISession
    _action: str
    _method: str
    _enctype: str
    _encoding: str
    prevalidationValues: Dict[Field, Optional[str]] = attr.ib(factory=dict)
    validationErrors: Dict[Field, ValidationError] = attr.ib(factory=dict)

    ENCTYPE_FORM_DATA = "multipart/form-data"
    ENCTYPE_URL_ENCODED = "application/x-www-form-urlencoded"

    def _fieldForCSRF(self) -> Field:
        """
        @return: A hidden L{Field} containing the cross-site request forgery
            protection token.
        """
        return Field.hidden(CSRF_PROTECTION, self._session.identifier)

    def _fieldsToRender(self) -> Iterable[Field]:
        """
        @return: an iterable of L{Field} objects to include in the HTML
            representation of this form.  This includes:

                - all the user-specified fields in the form

                - the CSRF protection hidden field

                - if no "submit" buttons are included in the form, one
                  additional field for a default submit button so the form can
                  be submitted.
        """
        anySubmit = False
        for field in self._form.fields:
            yield attr.assoc(
                field,
                value=self.prevalidationValues.get(field, field.value),
                error=self.validationErrors.get(field, None),
            )
            if field.formInputType == "submit":
                anySubmit = True
        if not anySubmit:
            yield Field(
                converter=str,
                formInputType="submit",
                value="submit",
                formFieldName="__klein_auto_submit__",
            )
        if self._method.lower() == "post":
            yield self._fieldForCSRF()

    # Public interface below.

    def lookupRenderMethod(self, name: str) -> NoReturn:
        """
        Form renderers don't supply any render methods, so this just always
        raises L{MissingRenderMethod}.
        """
        raise MissingRenderMethod(self, name)

    def render(self, request: IRequest) -> Tag:  # type: ignore[override]
        """
        Render this form to the given request.
        """
        formAttributes = {
            "accept-charset": self._encoding,
            "class": "klein-form",
        }
        if self._method.lower() == "post":
            # Enctype has no meaning on method="GET" forms.
            formAttributes.update(enctype=self._enctype)
        return tags.form(
            action=self._action, method=self._method, **formAttributes
        )(field.asTags() for field in self._fieldsToRender())

    def glue(self) -> List[Tag]:
        """
        Provide any glue necessary to render this form; this must be dropped
        into the template within the C{<form>} tag.

        Presently, this glue includes only the CSRF token argument, but Klein
        reserves the right to add arbitrary HTML here.  This should not create
        any user-visible content, however.

        @return: some HTML elements in the form of renderable objects for
            L{twisted.web.template}
        """
        return list(self._fieldForCSRF().asTags())


@bindable
def defaultValidationFailureHandler(
    instance: Optional[object],
    request: IRequest,
    fieldValues: "FieldValues",
) -> Element:
    """
    This is the default validation failure handler, which will be used by form
    handlers (i.e. any routes which use L{klein.Requirer} to require a field)
    in the case of any input validation failure when no other validation
    failure handler is registered via L{Form.onValidationFailureFor}.

    Its behavior is to simply return an HTML rendering of the form object,
    which includes inline information about fields which failed to validate.

    @param instance: The instance associated with the router that the form
        handler was handled on.
    @param request: The request including the form submission.
    @return: Any object acceptable from a Klein route.
    """
    session = cast(Componentized, request).getComponent(ISession)
    request.setResponseCode(400)
    enctype = (
        (
            request.getHeader(b"content-type")
            or RenderableForm.ENCTYPE_URL_ENCODED.encode("ascii")
        )
        .split(b";")[0]
        .decode("charmap")
    )
    renderable = RenderableForm(
        fieldValues.form,
        session,
        "/".join(
            segment.decode("utf-8", errors="replace")
            for segment in request.prepath
        ),
        request.method,
        enctype,
        "utf-8",
        fieldValues.prevalidationValues,
        fieldValues.validationErrors,
    )

    return Element(TagLoader(renderable))


_requirerFunctionWithForm = Any
_routeCallable = Any


class IProtoForm(Interface):
    """
    Marker interface for L{ProtoForm}.
    """

    fields: Sequence[Field] = Attribute("Form fields")

    def addField(field: Field) -> "FieldInjector":
        """
        Add the given field to the form ultimately created here.
        """


class IForm(Interface):
    """
    Marker interface for form attached to dependency injection components.
    """

    fields: Sequence[Field] = Attribute("Form fields")

    def populateRequestValues(
        injectionComponents: Componentized,
        instance: Any,
        request: IRequest,
    ) -> Deferred:
        """
        Extract the values present in this request and populate a
        L{FieldValues} object.
        """


@implementer(IProtoForm)
@attr.s(auto_attribs=True)
class ProtoForm:
    """
    Form-builder.
    """

    _componentized: Componentized
    _lifecycle: IRequestLifecycle
    fields: List[Field] = attr.ib(factory=list)

    @classmethod
    def fromComponentized(cls, componentized: Componentized) -> "ProtoForm":
        """
        Create a ProtoForm from a componentized object.
        """
        rl = IRequestLifecycle(componentized)
        assert rl is not None
        return cls(componentized, rl)

    def addField(self, field: Field) -> "FieldInjector":
        self.fields.append(field)
        return FieldInjector(self._componentized, field, self._lifecycle)


class IFieldValues(Interface):
    """
    Marker interface for parsed fields.
    """

    form: IForm = Attribute("Form")
    arguments: Dict[str, Any] = Attribute("Arguments")
    prevalidationValues: Dict[Field, Optional[str]] = Attribute(
        "Pre-validation values"
    )
    validationErrors: Dict[Field, ValidationError] = Attribute(
        "Validation errors"
    )

    def validate(instance: Any, request: IRequest) -> Deferred:
        """
        If any validation errors have occurred, raise a relevant exception.
        """


@implementer(IFieldValues)
@attr.s(auto_attribs=True)
class FieldValues:
    """
    Reified post-parsing values for HTTP form submission.
    """

    form: "Form"
    arguments: Dict[str, Any]
    prevalidationValues: Dict[Field, Optional[str]]
    validationErrors: Dict[Field, ValidationError]
    _injectionComponents: Componentized

    @inlineCallbacks
    def validate(
        self, instance: Any, request: IRequest
    ) -> Generator[Any, object, None]:
        if self.validationErrors:
            result = cast(
                KleinRenderable,
                (
                    yield _call(
                        instance,
                        IValidationFailureHandler(
                            self._injectionComponents,
                            defaultValidationFailureHandler,
                        ),
                        request,
                        self,
                    )
                ),
            )
            raise EarlyExit(result)


@implementer(IDependencyInjector)
@attr.s(auto_attribs=True)
class FieldInjector:
    """
    Field injector.
    """

    _componentized: Componentized
    _field: Field
    _lifecycle: IRequestLifecycle

    def injectValue(
        self, instance: Any, request: IRequest, routeParams: Dict[str, Any]
    ) -> Any:
        """
        Inject the given value into the form.
        """
        assert self._field.pythonArgumentName is not None
        return IFieldValues(request).arguments.get(
            self._field.pythonArgumentName
        )

    def finalize(self) -> None:
        """
        Finalize this ProtoForm into a real form.
        """
        if IForm(self._componentized, None) is not None:
            return

        finalForm = cast(IForm, Form(IProtoForm(self._componentized).fields))
        self._componentized.setComponent(IForm, finalForm)

        # XXX set requiresComponents argument here to ISession if CSRF is
        # required; add flag somewhere to indicate if a form is
        # side-effect-free (like a search field) that can be handled even
        # without a CSRF token.
        @bindable
        def populateValuesHook(instance: Any, request: IRequest) -> Deferred:
            return finalForm.populateRequestValues(
                self._componentized, instance, request
            )

        self._lifecycle.addPrepareHook(
            populateValuesHook,
            provides=[IFieldValues],
            requires=[ISession],
        )


registerAdapter(ProtoForm.fromComponentized, Componentized, IProtoForm)


class IValidationFailureHandler(Interface):
    """
    Validation failure handler callable interface.
    """

    def __call__(request: IRequest) -> KleinRenderable:
        """
        Called to handle a validation failure.
        """


def checkCSRF(request: IRequest) -> None:
    """
    Check the request for cross-site request forgery, raising an EarlyExit if
    it is found.
    """
    # TODO: optionalize CSRF protection for GET forms
    session = ISession(request, None)
    token = None
    if request.method in (b"GET", b"HEAD"):
        # Idempotent requests don't require CRSF validation.  (Don't have
        # destructive GETs or bad stuff will happen to you in general!)
        return
    if session is not None:
        if session.authenticatedBy == SessionMechanism.Header:
            # CSRF is possible because browsers automatically send cookies when
            # foreign domains provoke them into sending requests.  If a request
            # is authenticated by a header, then no checking is necessary.
            return
        # We have a session, we weren't authenticated by a header... time to
        # check that token.
        token = request.args.get(CSRF_PROTECTION.encode("ascii"), [b""])[
            0
        ].decode("ascii")
        if token == session.identifier:
            # The token matches.  We're OK.
            return
    # leak only the value passed, not the actual token, just in
    # case there's some additional threat vector there
    raise EarlyExit(CrossSiteRequestForgery(f"Invalid CSRF token: {token!r}"))


@implementer(IForm)
@attr.s(auto_attribs=True, hash=False)
class Form:
    """
    A L{Form} is a collection of fields attached to a function.
    """

    fields: Sequence[Field]

    @staticmethod
    def onValidationFailureFor(
        handler: _requirerFunctionWithForm,
    ) -> Callable[[Callable], Callable]:
        """
        Register a function to be run in the event of a validation failure for
        the input to a particular form handler.

        Generally used like so::

            requirer = Requirer(...)
            @requirer.prerequisite([ISession])
            def procureSession(request):
                return SessionProcurer(...).procureSession(request)
            router = Klein()
            @requirer.require(router.route("/", methods=['POST']),
                              someField=Field.text())
            def formHandler(someField):
                ...
            # Handle input validation failures for handleForm
            @Form.onValidationFailureFor(formHandler)
            def handleValidationFailures(request, fieldValues):
                return "Your inputs didn't validate."

        @see: L{defaultValidationFailureHandler} for a more detailed
            description of the decorated function's expected signature.  The
            additional parameter it is passed is a L{FieldValues} instance.

        @param handler: The form handler - i.e. function decorated by
            L{Form.handler} - for which the decorated function will handle
            validation failures.

        @return: a decorator that decorates a function with the signature
            C{(request, form) -> thing klein can render}.
        """

        def decorate(decoratee: Callable) -> Callable:
            handler.injectionComponents.setComponent(
                IValidationFailureHandler, decoratee
            )
            return decoratee

        return decorate

    @inlineCallbacks
    def populateRequestValues(
        self,
        injectionComponents: Componentized,
        instance: Any,
        request: IRequest,
    ) -> Generator[Any, object, None]:
        assert IFieldValues(request, None) is None

        validationErrors = {}
        prevalidationValues = {}
        arguments = {}

        checkCSRF(request)

        for field in self.fields:
            text = field.extractValue(request)
            prevalidationValues[field] = text
            try:
                value = field.validateValue(text)
                argName = field.pythonArgumentName
                if argName is None:
                    raise ValidationError("Form fields must all have names.")
            except ValidationError as ve:
                validationErrors[field] = ve
            else:
                arguments[argName] = value
        values = FieldValues(
            self,
            arguments,
            prevalidationValues,
            validationErrors,
            injectionComponents,
        )
        yield values.validate(instance, request)
        cast(Componentized, request).setComponent(IFieldValues, values)

    @classmethod
    def rendererFor(
        cls,
        decoratedFunction: _requirerFunctionWithForm,
        action: str,
        method: str = "POST",
        enctype: str = RenderableForm.ENCTYPE_FORM_DATA,
        encoding: str = "utf-8",
    ) -> "RenderableFormParam":
        """
        A form parameter that can render a form declared as a number of fields
        on another route.

        Use like so::

            class MyFormApp:
                router = Klein()
                requirer = Requirer()

                @requirer.require(
                    router.route("/handle-form", methods=["POST"]),
                    name=Field.text(), value=Field.integer(),
                )
                def formRoute(self, name, value):
                    ...

                @requirer.require(
                    router.route("/show-form", methods=["GET"]),
                    form=Form.rendererFor(formRoute)
                )
                def showForm(self, form):
                    return form

        As a L{RenderableForm} provides L{IRenderable}, you may return the
        parameter directly
        """
        form: Optional[IForm] = IForm(
            decoratedFunction.injectionComponents, None
        )
        if form is None:
            form = Form([])
        return RenderableFormParam(form, action, method, enctype, encoding)


@implementer(IRequiredParameter, IDependencyInjector)
@attr.s(auto_attribs=True)
class RenderableFormParam:
    """
    A L{RenderableFormParam} implements L{IRequiredParameter} and
    L{IDependencyInjector} to provide a L{RenderableForm} to your route.
    """

    _form: IForm
    _action: str
    _method: str
    _enctype: str
    _encoding: str

    def registerInjector(
        self,
        injectionComponents: Componentized,
        parameterName: str,
        requestLifecycle: IRequestLifecycle,
    ) -> "RenderableFormParam":
        return self

    def injectValue(
        self, instance: Any, request: IRequest, routeParams: Dict[str, Any]
    ) -> RenderableForm:
        """
        Create the renderable form from the request.
        """
        return RenderableForm(
            self._form,
            ISession(request),
            self._action,
            self._method,
            self._enctype,
            self._encoding,
            prevalidationValues={},
            validationErrors={},
        )

    def finalize(self) -> None:
        """
        Nothing to do upon finalization.
        """
