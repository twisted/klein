
from __future__ import print_function, unicode_literals

from itertools import count
from weakref import WeakKeyDictionary

import attr

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.python.compat import unicode
from twisted.web.error import MissingRenderMethod
from twisted.web.iweb import IRenderable
from twisted.web.template import Element, TagLoader, tags

from zope.interface import implementer

from ._app import _call
from ._decorators import bindable, modified
from ._interfaces import ISession, SessionMechanism

class CrossSiteRequestForgery(Exception):
    """
    Cross site request forgery detected.  Request aborted.
    """

CSRF_PROTECTION = "__csrf_protection__"

class ValidationError(Exception):
    """
    A L{ValidationError} is raised by L{Field.extractValue}.
    """

    def __init__(self, message):
        """
        Initialize a L{ValidationError} with a message to show to the user.
        """
        super(ValidationError, self).__init__(message)
        self.message = message


@attr.s(frozen=True)
class Field(object):
    """
    A L{Field} is a static part of a L{Form}.

    @ivar converter: The converter.
    """

    converter = attr.ib()
    formInputType = attr.ib()
    pythonArgumentName = attr.ib(default=None)
    formFieldName = attr.ib(default=None)
    formLabel = attr.ib(default=None)
    noLabel = attr.ib(default=False)
    value = attr.ib(default=u"")
    error = attr.ib(default=None)
    order = attr.ib(default=attr.Factory(lambda: next(count())))

    def maybeNamed(self, name):
        """
        Create a new L{Field} like this one, but with all the name default
        values filled in.

        @param name: the name.
        @type name: a native L{str}
        """
        def maybe(it, that=name):
            return that if it is None else it
        return attr.assoc(
            self,
            pythonArgumentName=maybe(self.pythonArgumentName),
            formFieldName=maybe(self.formFieldName),
            formLabel=maybe(self.formLabel,
                            name.capitalize() if not self.noLabel else None),
        )


    def asTags(self):
        """
        Convert this L{Field} into some stuff that can be rendered in a
        L{twisted.web.template}.

        @return: A new set of tags to include in a template.
        @rtype: iterable of L{twisted.web.template.Tag}
        """
        input_tag = tags.input(type=self.formInputType,
                               name=self.formFieldName, value=self.value)
        if self.formLabel:
            yield tags.label(self.formLabel, ": ", input_tag)
        else:
            yield input_tag
        if self.error:
            yield tags.div(self.error.message)


    def extractValue(self, request):
        """
        extract some bytes value from the request
        """
        return (request.args.get(self.formFieldName.encode("utf-8")) or
                [b""])[0]


    def validateValue(self, value):
        """
        Validate the given text and return a converted Python object to use, or
        fail with L{ValidationError}.
        """
        return self.converter(value)


    @classmethod
    def text(cls):
        """
        Shorthand for a form field that contains a short string, and will be
        rendered as a plain <input>.
        """
        return cls(converter=lambda x: unicode(x, "utf-8"),
                   formInputType="text")

    @classmethod
    def password(cls):
        """
        Shorthand for a form field that, like L{text}, contains a short string,
        but should be obscured when typed (and, to the extent possible,
        obscured in other sensitive contexts, such as logging.)
        """
        return cls(converter=lambda x: unicode(x, "utf-8"),
                   formInputType="password")

    @classmethod
    def hidden(cls, name, value):
        """
        Shorthand for a hidden field.
        """
        return cls(converter=lambda x: unicode(x, "utf-8"),
                   formInputType="hidden",
                   noLabel=True,
                   value=value).maybeNamed(name)


    @classmethod
    def integer(cls, minimum=None, maximum=None):
        """
        An integer within the range [minimum, maximum].
        """
        def bounded_int(text):
            try:
                value = int(text)
            except ValueError:
                raise ValidationError("must be an integer")
            else:
                if minimum is not None and value < minimum:
                    raise ValidationError("value must be >=" + repr(minimum))
                if maximum is not None and value > maximum:
                    raise ValidationError("value must be <=" + repr(maximum))
                return value
        return cls(converter=bounded_int, formInputType="number")



@implementer(IRenderable)
@attr.s
class RenderableForm(object):
    """
    An L{IRenderable} representing a renderable form.

    @ivar errors: a L{dict} mapping {L{Field}: L{ValidationError}}

    @ivar prevalidation: a L{dict} mapping {L{Field}: L{list} of L{unicode}},
        representing the value that each field received as part of the request.
    """
    _form = attr.ib()
    _session = attr.ib()
    _action = attr.ib()
    _method = attr.ib()
    _enctype = attr.ib()
    _encoding = attr.ib()
    prevalidation = attr.ib(default=attr.Factory(dict))
    errors = attr.ib(default=attr.Factory(dict))

    def _fieldForCSRF(self):
        """
        @return: A hidden L{Field} containing the cross-site request forgery
            protection token.
        """
        return Field.hidden(CSRF_PROTECTION, self._session.identifier)


    def _fieldsToRender(self):
        """
        @return: an interable of L{Field} objects to include in the HTML
            representation of this form.  This includes:

                - all the user-specified fields in the form

                - the CSRF protection hidden field

                - if no "submit" buttons are included in the form, one
                  additional field for a default submit button so the form can
                  be submitted.
        """
        any_submit = False
        for field in self._form._fields:
            yield attr.assoc(field,
                             value=self.prevalidation.get(field, field.value),
                             error=self.errors.get(field, None))
            if field.formInputType == "submit":
                any_submit = True
        if not any_submit:
            yield Field(str, formInputType="submit",
                        value=u"submit",
                        pythonArgumentName="submit",
                        formFieldName="submit")
        yield self._fieldForCSRF()

    # Public interface below.

    def lookupRenderMethod(self, name):
        """
        Form renderers don't supply any render methods, so this just always
        raises L{MissingRenderMethod}.
        """
        raise MissingRenderMethod(name)


    def render(self, request):
        """
        Render this form to the given request.
        """
        return (
            tags.form(action=self._action, method=self._method,
                      enctype=self._enctype,
                      **{"accept-charset": self._encoding})
            (
                field.asTags() for field in self._fieldsToRender()
            )
        )


    def glue(self):
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
def defaultValidationFailureHandler(instance, request, renderable):
    """
    This is the default validation failure handler, which will be used by
    L{Form.handler} in the case of any input validation failure when no other
    validation failure handler is registered via
    L{Form.onValidationFailureFor}.

    Its behavior is to simply return an HTML rendering of the form object,
    which includes inline information about fields which failed to validate.

    @param instance: The instance associated with the router that the form
        handler was handled on.
    @type instance: L{object}

    @param request: The request including the form submission.
    @type request: L{twisted.web.iweb.IRequest}

    @param renderable: The form, including any unrendered fields.
    @type renderable: L{RenderableForm}

    @return: Any object acceptable from a Klein route.
    """
    return Element(TagLoader(renderable))



@attr.s(hash=False)
class Form(object):
    """
    A L{Form} object which includes an authorizer, and may therefore be bound
    (via L{Form.bind}) to an individual session, producing a L{RenderableForm}.
    """
    _authorized = attr.ib()
    _fields = attr.ib(default=attr.Factory(list))

    def withFields(self, **fields):
        """
        Create a derived form with a series of fields.
        """
        return attr.evolve(
            self,
            fields=[
                field.maybeNamed(name) for name, field
                in sorted(fields.items(), key=lambda x: x[1].order)
            ]
        )


    ENCTYPE_FORM_DATA = b'multipart/form-data'
    ENCTYPE_URL_ENCODED = b'application/x-www-form-urlencoded'

    def onValidationFailureFor(self, handler):
        """
        Register a function to be run in the event of a validation failure for
        the input to a particular form handler.

        Generally used like so::

            myForm = Form(...).authorizedUsing(...)
            router = Klein()
            @myForm.handler(router.route("/", methods=['POST']))
            def handleForm(request, ...):
                ...

            # Handle input validation failures for handleForm
            @myForm.onValidationFailureFor(handleForm)
            def handleValidationFailures(request, formWithErrors):
                return "Your inputs didn't validate."

        @see: L{defaultValidationFailureHandler} for a more detailed
            description of the decorated function's expected signature.

        @param handler: The form handler - i.e. function decorated by
            L{Form.handler} - for which the decorated function will handle
            validation failures.

        @return: a decorator that decorates a function with the signature
            C{(request, form) -> thing klein can render}.
        """
        def decorate(decoratee):
            handler.validation_failureHandlers[self] = decoratee
            return decoratee
        return decorate


    def handler(self, route):
        """
        Declare a handler for a form.

        This is a decorator that takes a route.

        The function that it decorates should receive, as arguments, those
        parameters that C{route} would give it, in addition to parameters with
        the same names as all the L{Field}s in this L{Form}.

        For example::

            router = Klein()
            myForm = Form(authorized).withFields(value=Field.integer(),
                                                 name=Field.text())

            @myForm.handler(router.route("/", methods=["POST"]))
            def handleForm(request, value, name):
                return "form handled"
        """
        def decorator(function):
            vfhc = "validation_failureHandlers"
            failureHandlers = getattr(function, vfhc, WeakKeyDictionary())
            setattr(function, vfhc, failureHandlers)
            failureHandlers[self] = defaultValidationFailureHandler

            @modified("form handler", function,
                      self._authorized(route, __session__=ISession))
            @bindable
            @inlineCallbacks
            def decoratedHandler(instance, request, *args, **kw):
                session = kw.pop("__session__")
                if session.authenticatedBy == SessionMechanism.Cookie:
                    token = request.args.get(CSRF_PROTECTION.encode("ascii"),
                                             [b""])[0]
                    token = token.decode("ascii")
                    if token != session.identifier:
                        raise CrossSiteRequestForgery(token,
                                                      session.identifier)
                validationErrors = {}
                prevalidation_values = {}
                arguments = {}
                for field in self._fields:
                    text = field.extractValue(request)
                    prevalidation_values[field] = text
                    try:
                        value = field.validateValue(text)
                    except ValidationError as ve:
                        validationErrors[field] = ve
                    else:
                        arguments[field.pythonArgumentName] = value
                if validationErrors:
                    renderable = RenderableForm(
                        self, session, b"/".join(request.prepath),
                        request.method,
                        request.getHeader(u'content-type').split(u';')[0],
                        prevalidation=prevalidation_values,
                        errors=validationErrors,
                    )
                    result = yield _call(instance, failureHandlers[self],
                                         request, renderable, *args, **kw)
                else:
                    kw.update(arguments)
                    result = yield _call(instance, function, request,
                                         *args, **kw)
                returnValue(result)
            return function
        return decorator


    def renderer(self, route, action, method="POST", enctype=ENCTYPE_FORM_DATA,
                 argument="form", encoding="utf-8"):
        def decorator(function):
            @modified("form renderer", function,
                      self._authorized(route, __session__=ISession))
            @bindable
            @inlineCallbacks
            def renderer_decorated(instance, request, *args, **kw):
                session = kw.pop("__session__")
                form = RenderableForm(self, session, action, method, enctype,
                                      prevalidation={},
                                      errors={}, encoding=encoding)
                kw[argument] = form
                result = yield _call(instance, function, request, *args, **kw)
                returnValue(result)
            return function
        return decorator
