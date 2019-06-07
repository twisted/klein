# -*- test-case-name: klein.test.test_form -*-

from __future__ import print_function, unicode_literals

import json
from typing import (
    Any, AnyStr, Callable, Dict, Iterable, List, Optional, Sequence,
    TYPE_CHECKING, Text, Union, cast
)

import attr

from twisted.internet.defer import inlineCallbacks
from twisted.python.compat import unicode
from twisted.python.components import Componentized, registerAdapter
from twisted.web.error import MissingRenderMethod
from twisted.web.http import FORBIDDEN
from twisted.web.iweb import IRenderable, IRequest
from twisted.web.resource import Resource
from twisted.web.template import Element, Tag, TagLoader, tags

from zope.interface import Interface, implementer

from ._app import _call
from ._decorators import bindable
from .interfaces import (EarlyExit, IDependencyInjector, IRequestLifecycle,
                         IRequiredParameter, ISession, SessionMechanism,
                         ValidationError, ValueAbsent)

if TYPE_CHECKING:               # pragma: no cover
    from typing import Type
    from mypy_extensions import DefaultNamedArg, NoReturn
    from twisted.internet.defer import Deferred
    if not TYPE_CHECKING:
        (Tag, Any, Callable, Dict, Optional, AnyStr, Iterable, IRequest, List,
         Text, DefaultNamedArg, Union, NoReturn, Deferred, Type)
else:
    def DefaultNamedArg(*ignore):
        pass

class CrossSiteRequestForgery(Resource, object):
    """
    Cross site request forgery detected.  Request aborted.
    """
    def __init__(self, message):
        # type: (str) -> None
        super(CrossSiteRequestForgery, self).__init__()
        self.message = message

    def render(self, request):
        # type: (IRequest) -> bytes
        """
        For all HTTP methods, return a 403.
        """
        request.setResponseCode(FORBIDDEN, b"FAILURECSRF")
        return ("CSRF TOKEN FAILURE: " + self.message).encode("utf-8")

CSRF_PROTECTION = "__csrf_protection__"

def textConverter(value):
    # type: (AnyStr) -> Text
    """
    Converter for form values (which may be any type of string) into text.
    """
    return (
        value if isinstance(value, unicode) else unicode(value, "utf-8")
    )



class IParsedJSONBody(Interface):
    """
    Marker interface for the dict parsed from the request body's JSON contents.
    """
    # TODO: how to allow applications to pass options to loads, such as
    # parse_float?



@implementer(IRequiredParameter)
@attr.s(frozen=True)
class Field(object):
    """
    A L{Field} is a static part of a L{Form}.

    @ivar converter: The converter.
    """

    converter = attr.ib(type=Callable[[AnyStr], Any])
    formInputType = attr.ib(type=str)
    pythonArgumentName = attr.ib(type=Optional[str], default=None)
    formFieldName = attr.ib(type=Optional[str], default=None)
    formLabel = attr.ib(type=Optional[str], default=None)
    default = attr.ib(type=Optional[Any], default=None, cmp=False)
    required = attr.ib(type=bool, default=True)
    noLabel = attr.ib(type=bool, default=False)
    value = attr.ib(type=Text, default=u"")
    error = attr.ib(type=ValidationError, default=None)

    # IRequiredParameter
    def registerInjector(self, injectionComponents, parameterName,
                         requestLifecycle):
        # type: (Componentized, str, IRequestLifecycle) -> IDependencyInjector
        """
        Register this form field as a dependency injector.
        """
        protoForm = IProtoForm(injectionComponents)
        return protoForm.addField(self.maybeNamed(parameterName))


    def maybeNamed(self, name):
        # type: (str) -> Field
        """
        Create a new L{Field} like this one, but with all the name default
        values filled in.

        @param name: the name.
        @type name: a native L{str}
        """
        def maybe(it, that=name):
            # type: (Optional[str], Optional[str]) -> Optional[str]
            return that if it is None else it
        return attr.assoc(
            self,
            pythonArgumentName=maybe(self.pythonArgumentName),
            formFieldName=maybe(self.formFieldName),
            formLabel=maybe(self.formLabel,
                            name.capitalize() if not self.noLabel else None),
        )


    def asTags(self):
        # type: () -> Iterable[Tag]
        """
        Convert this L{Field} into some stuff that can be rendered in a
        L{twisted.web.template}.

        @return: A new set of tags to include in a template.
        @rtype: iterable of L{twisted.web.template.Tag}
        """
        input_tag = tags.input(
            type=self.formInputType, name=self.formFieldName,
            value=(self.value if self.value is not None else "")
        )
        error_tags = []
        if self.error:
            error_tags.append(tags.div(class_="klein-form-validation-error")
                              (self.error.message))
        if self.formLabel:
            yield tags.label(self.formLabel, ": ", input_tag, *error_tags)
        else:
            yield input_tag
            yield error_tags

    def extractValue(self, request):
        # type: (IRequest) -> Any
        """
        Extract a value from the request.

        In the case of key/value form posts, this attempts to reliably make the
        value into Text.  In the case of a JSON post, however, it will simply
        extract the value from the top-level dictionary, which means it could
        be any arrangement of JSON-serializiable objects.
        """
        fieldName = self.formFieldName
        if fieldName is None:
            raise ValueError("Cannot extract unnamed form field.")
        contentType = request.getHeader(b"content-type")
        if (
                contentType is not None and
                contentType.startswith(b'application/json')
        ):
            # TODO: parse only once, please.
            parsed = request.getComponent(IParsedJSONBody)
            if parsed is None:
                request.content.seek(0)
                octets = request.content.read()
                characters = octets.decode("utf-8")
                parsed = json.loads(characters)
                request.setComponent(IParsedJSONBody, parsed)
            if fieldName not in parsed:
                return None
            return parsed[fieldName]
        allValues = request.args.get(fieldName.encode("utf-8"))
        if allValues:
            return allValues[0].decode('utf-8')
        else:
            return None


    def validateValue(self, value):
        # type: (Any) -> Any
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
    def text(cls, **kw):              # type: (**Any) -> Field
        """
        Shorthand for a form field that contains a short string, and will be
        rendered as a plain <input>.
        """
        return cls(converter=textConverter, formInputType="text", **kw)

    @classmethod
    def password(cls, **kw):          # type: (**Any) -> Field
        """
        Shorthand for a form field that, like L{text}, contains a short string,
        but should be obscured when typed (and, to the extent possible,
        obscured in other sensitive contexts, such as logging.)
        """
        return cls(converter=textConverter,
                   formInputType="password", **kw)

    @classmethod
    def hidden(cls, name, value, **kw):
        # type: (str, Text, **Any) -> Field
        """
        Shorthand for a hidden field.
        """
        return cls(converter=textConverter,
                   formInputType="hidden",
                   noLabel=True,
                   value=value, **kw).maybeNamed(name)


    @classmethod
    def number(cls, minimum=None, maximum=None, kind=float, **kw):
        # type: (Optional[int], Optional[int], Type, **Any) -> Field
        """
        An integer within the range [minimum, maximum].
        """
        def bounded_number(text):
            # type: (AnyStr) -> Any
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
    def submit(cls, value):
        # type: (Text) -> Field
        """
        A field representing a submit button, with a value (displayed on the
        button).
        """
        return cls(converter=textConverter, formInputType="submit",
                   noLabel=True, default=value)



@implementer(IRenderable)
@attr.s
class RenderableForm(object):
    """
    An L{IRenderable} representing a renderable form.

    @ivar prevalidationValues: a L{dict} mapping {L{Field}: L{list} of
        L{unicode}}, representing the value that each field received as part of
        the request.

    @ivar validationErrors: a L{dict} mapping {L{Field}: L{ValidationError}}
    """
    _form = attr.ib(type='Form')
    _session = attr.ib(type=ISession)
    _action = attr.ib(type=str)
    _method = attr.ib(type=str)
    _enctype = attr.ib(type=str)
    _encoding = attr.ib(type=str)
    prevalidationValues = attr.ib(
        type=Dict[Field, Optional[Text]],
        default=cast(Dict[Field, Optional[Text]], attr.Factory(dict))
    )
    validationErrors = attr.ib(
        type=Dict[Field, ValidationError],
        default=cast(Dict[Field, ValidationError], attr.Factory(dict))
    )

    ENCTYPE_FORM_DATA = 'multipart/form-data'
    ENCTYPE_URL_ENCODED = 'application/x-www-form-urlencoded'

    def _fieldForCSRF(self):
        # type: () -> Field
        """
        @return: A hidden L{Field} containing the cross-site request forgery
            protection token.
        """
        return Field.hidden(CSRF_PROTECTION, self._session.identifier)


    def _fieldsToRender(self):
        # type: () -> Iterable[Field]
        """
        @return: an interable of L{Field} objects to include in the HTML
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
                error=self.validationErrors.get(field, None)
            )
            if field.formInputType == "submit":
                anySubmit = True
        if not anySubmit:
            yield Field(converter=str, formInputType="submit", value=u"submit",
                        formFieldName="__klein_auto_submit__")
        if self._method.lower() == 'post':
            yield self._fieldForCSRF()

    # Public interface below.

    def lookupRenderMethod(self, name):
        # type: (str) -> NoReturn
        """
        Form renderers don't supply any render methods, so this just always
        raises L{MissingRenderMethod}.
        """
        raise MissingRenderMethod(self, name)


    def render(self, request):
        # type: (IRequest) -> Tag
        """
        Render this form to the given request.
        """
        formAttributes = {"accept-charset": self._encoding,
                          "class": "klein-form"}
        if self._method.lower() == 'post':
            # Enctype has no meaning on method="GET" forms.
            formAttributes.update(enctype=self._enctype)
        return (
            tags.form(action=self._action, method=self._method,
                      **formAttributes)
            (
                field.asTags() for field in self._fieldsToRender()
            )
        )


    def glue(self):
        # type: () -> Iterable[Tag]
        """
        Provide any glue necessary to render this form; this must be dropped
        into the template within the C{<form>} tag.

        Presently, this glue includes only the CSRF token argument, but Klein
        reserves the right to add arbitrary HTML here.  This should not create
        any user-visible content, however.

        @return: some HTML elements in the form of renderable objects for
            L{twisted.web.template}
        @rtype: L{twisted.web.template.Tag}, or L{list} thereof.
        """
        return self._fieldForCSRF().asTags()



@bindable
def defaultValidationFailureHandler(
        instance,               # type: Optional[object]
        request,                # type: IRequest
        fieldValues,            # type: FieldValues
):
    # type: (...) -> Element
    """
    This is the default validation failure handler, which will be used by form
    handlers (i.e. any routes which use L{klein.Requirer} to require a field)
    in the case of any input validation failure when no other validation
    failure handler is registered via L{Form.onValidationFailureFor}.

    Its behavior is to simply return an HTML rendering of the form object,
    which includes inline information about fields which failed to validate.

    @param instance: The instance associated with the router that the form
        handler was handled on.
    @type instance: L{object}

    @param request: The request including the form submission.
    @type request: L{twisted.web.iweb.IRequest}

    @return: Any object acceptable from a Klein route.
    """
    session = request.getComponent(ISession)
    request.setResponseCode(400)
    enctype = (
        (request.getHeader(b'content-type') or
         RenderableForm.ENCTYPE_URL_ENCODED.encode("ascii"))
        .split(b';')[0].decode("charmap")
    )
    renderable = RenderableForm(
        fieldValues.form, session, u"/".join(
            segment.decode("utf-8", errors='replace')
            for segment in request.prepath
        ),
        request.method, enctype, "utf-8", fieldValues.prevalidationValues,
        fieldValues.validationErrors,
    )

    return Element(TagLoader(renderable))


_requirerFunctionWithForm = Any
_routeCallable = Any
_routeDecorator = Callable[
    [_routeCallable, DefaultNamedArg(Any, '__session__')],
    _routeCallable
]
_validationFailureHandler = Callable[
    [Optional[object], IRequest, 'Form', Dict[str, str]], Element
]

validationFailureHandlerAttribute = "__kleinFormValidationFailureHandlers__"


class IProtoForm(Interface):
    """
    Marker interface for L{ProtoForm}.
    """

class IForm(Interface):
    """
    Marker interface for form attached to dependency injection components.
    """


@implementer(IProtoForm)
@attr.s
class ProtoForm(object):
    """
    Form-builder.
    """
    _componentized = attr.ib(type=Componentized)
    _lifecycle = attr.ib(type=IRequestLifecycle)
    _fields = attr.ib(type=List[Field], default=attr.Factory(list))

    @classmethod
    def fromComponentized(cls, componentized):
        # type: (Componentized) -> ProtoForm
        """
        Create a ProtoForm from a componentized object.
        """
        rl = IRequestLifecycle(componentized)
        assert rl is not None
        return cls(componentized, rl)


    def addField(self, field):
        # type: (Field) -> FieldInjector
        """
        Add the given field to the form ultimately created here.
        """
        self._fields.append(field)
        return FieldInjector(self._componentized, field, self._lifecycle)



class IFieldValues(Interface):
    """
    Marker interface for parsed fields.
    """



@implementer(IFieldValues)
@attr.s
class FieldValues(object):
    """
    Reified post-parsing values for HTTP form submission.
    """

    form = attr.ib(type='Form')
    arguments = attr.ib(type=Dict[str, Any])
    prevalidationValues = attr.ib(type=Dict[Field, Optional[Text]])
    validationErrors = attr.ib(type=Dict[Field, ValidationError])
    _injectionComponents = attr.ib(type=Componentized)

    @inlineCallbacks
    def validate(self, instance, request):
        # type: (Any, IRequest) -> Deferred
        """
        If any validation errors have occurred, raise a relevant exception.
        """
        if self.validationErrors:
            result = yield _call(
                instance,
                IValidationFailureHandler(self._injectionComponents,
                                          defaultValidationFailureHandler),
                request, self
            )
            raise EarlyExit(result)



@implementer(IDependencyInjector)
@attr.s
class FieldInjector(object):
    """
    Field injector.
    """
    _componentized = attr.ib(type=Componentized)
    _field = attr.ib(type=Field)
    _lifecycle = attr.ib(type=IRequestLifecycle)

    def injectValue(self, instance, request, routeParams):
        # type: (Any, IRequest, Dict[str, Any]) -> Any
        """
        Inject the given value into the form.
        """
        return IFieldValues(request).arguments.get(
            self._field.pythonArgumentName
        )

    def finalize(self):
        # type: () -> None
        """
        Finalize this ProtoForm into a real form.
        """
        finalForm = IForm(self._componentized, None)
        if finalForm is not None:
            return
        finalForm = Form(IProtoForm(self._componentized)._fields)
        self._componentized.setComponent(IForm, finalForm)

        # XXX set requiresComponents argument here to ISession if CSRF is
        # required; add flag somewhere to indicate if a form is
        # side-effect-free (like a search field) that can be handled even
        # without a CSRF token.
        @bindable
        def populateValuesHook(instance, request):
            # type: (Any, IRequest) -> Deferred
            return finalForm.populateRequestValues(
                self._componentized, instance, request
            )
        self._lifecycle.addPrepareHook(
            populateValuesHook, provides=[IFieldValues],
            requires=[ISession]
        )



registerAdapter(ProtoForm.fromComponentized, Componentized, IProtoForm)



class IValidationFailureHandler(Interface):
    """
    Validation failure handler callable interface.
    """


def checkCSRF(request):
    # type: (IRequest) -> None
    """
    Check the request for cross-site request forgery, raising an EarlyExit if
    it is found.
    """
    # TODO: optionalize CSRF protection for GET forms
    session = ISession(request, None)
    token = None
    if request.method in (b'GET', b'HEAD'):
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
        token = (request.args.get(CSRF_PROTECTION.encode("ascii"), [b""])[0]
                 .decode("ascii"))
        if token == session.identifier:
            # The token matches.  We're OK.
            return
    # leak only the value passed, not the actual token, just in
    # case there's some additional threat vector there
    raise EarlyExit(CrossSiteRequestForgery(
        "Invalid CSRF token: {!r}".format(token)
    ))



@attr.s(hash=False)
class Form(object):
    """
    A L{Form} is a collection of fields attached to a function.
    """
    fields = attr.ib(type=Sequence[Field])

    @staticmethod
    def onValidationFailureFor(handler):
        # type: (_requirerFunctionWithForm) -> Callable[[Callable], Callable]
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
        def decorate(decoratee):
            # type: (Callable) -> Callable
            handler.injectionComponents.setComponent(IValidationFailureHandler,
                                                     decoratee)
            return decoratee
        return decorate


    @inlineCallbacks
    def populateRequestValues(self, injectionComponents, instance, request):
        # type: (Componentized, Any, IRequest) -> Deferred
        """
        Extract the values present in this request and populate a
        L{FieldValues} object.
        """
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
        values = FieldValues(self, arguments, prevalidationValues,
                             validationErrors, injectionComponents)
        yield values.validate(instance, request)
        request.setComponent(IFieldValues, values)


    @classmethod
    def rendererFor(
        cls,
        decoratedFunction,  # type: _requirerFunctionWithForm
        action,             # type: Text
        method=u"POST",     # type: Text
        enctype=RenderableForm.ENCTYPE_FORM_DATA,  # type: Text
        encoding="utf-8"                           # type: str
    ):
        # type: (...) -> RenderableFormParam
        """
        A form parameter that can render a form declared as a number of fields
        on another route.

        Use like so::

            class MyFormApp(object):
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
        form = IForm(decoratedFunction.injectionComponents, None)
        if form is None:
            form = Form([])
        return RenderableFormParam(form, action, method, enctype, encoding)



@implementer(IRequiredParameter, IDependencyInjector)
@attr.s
class RenderableFormParam(object):
    """
    A L{RenderableFormParam} implements L{IRequiredParameter} and
    L{IDependencyInjector} to provide a L{RenderableForm} to your route.
    """

    _form = attr.ib(type=Form)
    _action = attr.ib(type=Text)
    _method = attr.ib(type=Text)
    _enctype = attr.ib(type=Text)
    _encoding = attr.ib(type=Text)

    def registerInjector(self, injectionComponents, parameterName,
                         requestLifecycle):
        # type: (Componentized, str, IRequestLifecycle) -> RenderableFormParam
        return self

    def injectValue(self, instance, request, routeParams):
        # type: (Any, IRequest, Dict[str, Any]) -> RenderableForm
        """
        Create the renderable form from the request.
        """
        return RenderableForm(
            self._form, ISession(request), self._action, self._method,
            self._enctype, self._encoding, prevalidationValues={},
            validationErrors={}
        )

    def finalize(self):
        # type: () -> None
        """
        Nothing to do upon finalization.
        """
