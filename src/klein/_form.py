
from __future__ import unicode_literals, print_function

import attr

from zope.interface import implementer

from twisted.python.compat import unicode
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.template import tags
from twisted.web.iweb import IRenderable
from twisted.web.error import MissingRenderMethod

from klein.interfaces import SessionMechanism
from klein.app import _call

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
class FormRenderer(object):
    """
    @ivar errors: a L{dict} mapping {L{Field}: L{ValidationError}}

    @ivar prevalidation: a L{dict} mapping {L{Field}: L{list} of L{unicode}},
        representing the value that each field received as part of the request.
    """
    form = attr.ib()
    session = attr.ib()
    action = attr.ib()
    method = attr.ib()
    enctype = attr.ib()
    encoding = attr.ib(default="utf-8")
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
        
        """
        return (
            tags.form(action=self.action, method=self.method,
                      enctype=self.enctype)
            (
                field.as_tags() for field in self._fields_to_render()
            )
        )


    def csrf(self):
        """
        
        """
        return self._csrf_field().as_tags()


    def _csrf_field(self):
        """
        
        """
        return Form.hidden(CSRF_PROTECTION, self.session.identifier)


    def _fields_to_render(self):
        """
        
        """
        any_submit = False
        for field in self.form.fields.values():
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



def default_validation_failure_handler(instance, ):
    """
    
    """
    



default_validation_failure_handler.__klein_bound__ = True

@attr.s(init=False)
class Form(object):
    """
    
    """
    fields = attr.ib()

    form_data = b'multipart/form-data'
    url_encoded = b'application/x-www-form-urlencoded'

    def __init__(self, fields, procurer_from_request):
        """
        
        """
        self.fields = {
            name: field.maybe_named(name)
            for name, field in fields.items()
        }
        self.procurer_from_request = procurer_from_request
        self.validation_failure_handlers = {}


    def on_validation_failure_for(self, an_handler):
        """
        
        """
        def decorate(decoratee):
            an_handler.validation_failure_handler_container[:] = [decoratee]
            return decoratee
        return decorate


    def handler(self, route):
        """
        
        """
        def decorator(function):
            @route
            @inlineCallbacks
            def handler_decorated(instance, request, *args, **kw):
                procurer = _call(instance, self.procurer_from_request,
                                 request)
                session = yield procurer.procure_session()
                if session.authenticated_by == SessionMechanism.Cookie:
                    token = request.args.get(CSRF_PROTECTION, [None])[0]
                    if token != session.identifier:
                        raise CrossSiteRequestForgery(token,
                                                      session.identifier)
                validation_errors = {}
                prevalidation_values = {}
                arguments = {}
                for field in self.fields.values():
                    text = field.extract_value(request)
                    prevalidation_values[field] = text
                    try:
                        value = field.validate_value(text)
                    except ValidationError as ve:
                        validation_errors[field] = ve
                    else:
                        arguments[field.python_argument_name] = value
                if validation_errors:
                    # XXX need a better name than "renderer" probably?
                    form_renderer = FormRenderer(
                        self, session, b"/".join(request.prepath),
                        request.method,
                        request.getHeader('content-type').decode('utf-8').split(';')[0],
                        prevalidation=prevalidation_values,
                        errors=validation_errors,
                    )
                    if function.validation_failure_handler_container:
                        [handler] = (
                            function.validation_failure_handler_container
                        )
                    else:
                        handler = default_validation_failure_handler
                    result = yield _call(instance, handler, request,
                                         form_renderer, *args, **kw)
                else:
                    kw.update(arguments)
                    result = yield _call(instance, function, request,
                                         *args, **kw)
                returnValue(result)
            handler_decorated.__klein_bound__ = True
            # we can't use the function itself as a dictionary key, because
            # Plating (or another, similar system) might have decorated it to
            # make the route behave differently.  but Plating preserves
            # attributes set here across into the real handler.
            function.validation_failure_handler_container = []
            return function
        return decorator


    def renderer(self, route, action, method="POST", enctype=form_data,
                 argument="form"):
        """
        
        """
        def decorator(function):
            @route
            @inlineCallbacks
            def renderer_decorated(instance, request, *args, **kw):
                procurer = self.procurer_from_request(request)
                session = yield procurer.procure_session()
                form = FormRenderer(self, session, action, method, enctype)
                kw[argument] = form
                result = yield _call(instance, function, request, *args, **kw)
                returnValue(result)
            renderer_decorated.__klein_bound__ = True
            return function
        return decorator


    @staticmethod
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


    @staticmethod
    def text():
        """
        
        """
        return Field(converter=lambda x: unicode(x, "utf-8"),
                     form_input_type="text")


    @staticmethod
    def password():
        """
        
        """
        return Field(converter=lambda x: unicode(x, "utf-8"),
                     form_input_type="password")


    @staticmethod
    def hidden(name, value):
        """
        
        """
        return Field(converter=lambda x: unicode(x, "utf-8"),
                     form_input_type="hidden",
                     no_label=True,
                     value=value).maybe_named(name)

