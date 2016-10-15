
from __future__ import unicode_literals, print_function

import attr

from weakref import WeakKeyDictionary
from itertools import count

from zope.interface import implementer

from twisted.python.compat import unicode
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.template import tags
from twisted.web.iweb import IRenderable
from twisted.web.error import MissingRenderMethod

from .interfaces import SessionMechanism, ISession
from .app import _call
from ._decorators import bindable, modified

class CrossSiteRequestForgery(Exception):
    """
    Cross site request forgery detected.  Request aborted.
    """

CSRF_PROTECTION = "__csrf_protection__"

class ValidationError(Exception):
    """
    A L{ValidationError} is raised by L{Field.extract_value}.
    """

    def __init__(self, message):
        """
        Initialize a L{ValidationError} with a message to show to the user.
        """
        super(ValidationError, self).__init__(message)
        self.message = message


@attr.s
class Field(object):
    """
    A L{Field} is a static part of a L{Form}.

    @ivar converter: The converter.
    """

    converter = attr.ib()
    form_input_type = attr.ib()
    python_argument_name = attr.ib(default=None)
    form_field_name = attr.ib(default=None)
    form_label = attr.ib(default=None)
    no_label = attr.ib(default=False)
    value = attr.ib(default=u"")
    error = attr.ib(default=None)
    order = attr.ib(default=attr.Factory(lambda: next(count())))

    def maybe_named(self, name):
        """
        Create a new L{Field} like this one, but with all the name default
        values filled in.

        @param name: the name.
        @type name: a native L{str}
        """
        maybe = lambda it, that=name: that if it is None else it
        return attr.assoc(
            self,
            python_argument_name=maybe(self.python_argument_name),
            form_field_name=maybe(self.form_field_name),
            form_label=maybe(self.form_label,
                             name.capitalize() if not self.no_label else None),
        )


    def as_tags(self):
        """
        
        """
        input_tag = tags.input(type=self.form_input_type,
                               name=self.form_field_name, value=self.value)
        if self.form_label:
            yield tags.label(self.form_label, ": ", input_tag)
        else:
            yield input_tag
        if self.error:
            yield tags.div(self.error.message)


    def extract_value(self, request):
        """
        extract some bytes value from the request
        """
        return (request.args.get(self.form_field_name) or [b""])[0]


    def validate_value(self, value):
        """
        Validate the given text and return a converted Python object to use, or
        fail with L{ValidationError}.
        """
        return self.converter(value)



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

    def _csrf_field(self):
        """
        
        """
        return hidden(CSRF_PROTECTION, self._session.identifier)


    def _fields_to_render(self):
        """
        
        """
        any_submit = False
        for field in self._form._fields:
            yield attr.assoc(field,
                             value=self.prevalidation.get(field, field.value),
                             error=self.errors.get(field, None))
            if field.form_input_type == "submit":
                any_submit = True
        if not any_submit:
            yield Field(str, form_input_type="submit",
                        value=u"submit",
                        python_argument_name="submit",
                        form_field_name="submit")
        yield self._csrf_field()

    # Public interface below.

    prevalidation = attr.ib(default=attr.Factory(dict))
    errors = attr.ib(default=attr.Factory(dict))

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
                field.as_tags() for field in self._fields_to_render()
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
        return self._csrf_field().as_tags()


@bindable
def default_validation_failure_handler(instance, request, renderable):
    """
    
    """
    from twisted.web.template import Element, TagLoader
    return Element(TagLoader(renderable))



FORM_DATA = b'multipart/form-data'
URL_ENCODED = b'application/x-www-form-urlencoded'


@attr.s(hash=False)
class BindableForm(object):
    """
    
    """
    _fields = attr.ib()
    _authorized = attr.ib()

    def on_validation_failure_for(self, an_handler):
        """
        
        """
        def decorate(decoratee):
            an_handler.validation_failure_handlers[self] = decoratee
            return decoratee
        return decorate


    def handler(self, route):
        """
        
        """
        def decorator(function):
            vfhc = "validation_failure_handlers"
            failure_handlers = getattr(function, vfhc, WeakKeyDictionary())
            setattr(function, vfhc, failure_handlers)
            failure_handlers[self] = default_validation_failure_handler
            @modified("form handler", function,
                      self._authorized(route, __session__=ISession))
            @bindable
            @inlineCallbacks
            def handler_decorated(instance, request, *args, **kw):
                session = kw.pop("__session__")
                if session.authenticated_by == SessionMechanism.Cookie:
                    token = request.args.get(CSRF_PROTECTION, [None])[0]
                    if token != session.identifier:
                        raise CrossSiteRequestForgery(token,
                                                      session.identifier)
                validation_errors = {}
                prevalidation_values = {}
                arguments = {}
                for field in self._fields:
                    text = field.extract_value(request)
                    prevalidation_values[field] = text
                    try:
                        value = field.validate_value(text)
                    except ValidationError as ve:
                        validation_errors[field] = ve
                    else:
                        arguments[field.python_argument_name] = value
                if validation_errors:
                    renderable = self.bind(
                        session, b"/".join(request.prepath),
                        request.method,
                        (request.getHeader('content-type')
                         .decode('utf-8').split(';')[0]),
                        prevalidation=prevalidation_values,
                        errors=validation_errors,
                    )
                    result = yield _call(instance, failure_handlers[self],
                                         request, renderable, *args, **kw)
                else:
                    kw.update(arguments)
                    result = yield _call(instance, function, request,
                                         *args, **kw)
                returnValue(result)
            return function
        return decorator


    def renderer(self, route, action, method="POST", enctype=FORM_DATA,
                 argument="form", encoding="utf-8"):
        def decorator(function):
            @modified("form renderer", function,
                      self._authorized(route, __session__=ISession))
            @bindable
            @inlineCallbacks
            def renderer_decorated(instance, request, *args, **kw):
                session = kw.pop("__session__")
                form = self.bind(session, action, method, enctype,
                                 encoding=encoding)
                kw[argument] = form
                result = yield _call(instance, function, request, *args, **kw)
                returnValue(result)
            return function
        return decorator


    def bind(self, session, action, method="POST", enctype=FORM_DATA,
             prevalidation=None, errors=None, encoding="utf-8"):
        """
        Bind this form to a session.
        """
        if prevalidation is None:
            prevalidation = {}
        if errors is None:
            errors = {}
        return RenderableForm(self, session, action, method, enctype,
                              prevalidation=prevalidation,
                              errors=errors, encoding=encoding)



@attr.s(hash=False)
class Form(object):
    """
    
    """
    _fields = attr.ib()

    def authorized_using(self, authorized):
        """
        
        """
        return BindableForm(self._fields, authorized)



def form(*fields, **named_fields):
    """
    Create a form.
    """
    return Form(list(fields) + [
        field.maybe_named(name) for name, field
        in sorted(named_fields.items(), key=lambda x: x[1].order)
    ])


def add(it):
    """
    
    """
    setattr(form, it.__name__, it)
    return it


@add
def text():
    """

    """
    return Field(converter=lambda x: unicode(x, "utf-8"),
                 form_input_type="text")

@add
def password():
    """

    """
    return Field(converter=lambda x: unicode(x, "utf-8"),
                 form_input_type="password")

@add
def hidden(name, value):
    """

    """
    return Field(converter=lambda x: unicode(x, "utf-8"),
                 form_input_type="hidden",
                 no_label=True,
                 value=value).maybe_named(name)


@add
def integer(minimum=None, maximum=None):
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
    return Field(converter=bounded_int, form_input_type="number")
