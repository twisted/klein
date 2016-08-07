
import attr

from zope.interface import implementer

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.template import tags, MissingRenderMethod
from twisted.web.iweb import IRenderable

from klein.interfaces import SessionMechanism
from klein.app import _call

class CrossSiteRequestForgery(Exception):
    """
    Cross site request forgery detected.  Request aborted.
    """

CSRF_PROTECTION = "__csrf_protection__"

@attr.s
class Field(object):
    """
    
    """

    coercer = attr.ib()
    form_input_type = attr.ib()
    python_argument_name = attr.ib(default=None)
    form_field_name = attr.ib(default=None)
    form_label = attr.ib(default=None)
    no_label = attr.ib(default=False)
    value = attr.ib(default=u"")

    def maybe_named(self, name):
        """
        
        """
        if self.python_argument_name is None:
            self.python_argument_name = name
        if self.form_field_name is None:
            self.form_field_name = name
        if self.form_label is None and not self.no_label:
            self.form_label = name.capitalize()
        return self


    def as_tags(self):
        """
        
        """
        input_tag = tags.input(type=self.form_input_type,
                               name=self.form_field_name,
                               value=self.value)
        if self.form_label:
            return tags.label(self.form_label, ": ", input_tag)
        else:
            return input_tag


    def extract_from_request(self, request):
        """
        
        """
        return self.coercer(request.args.get(self.form_field_name)[0])



@implementer(IRenderable)
@attr.s
class FormRenderer(object):
    """
    
    """
    form = attr.ib()
    procurer = attr.ib()
    action = attr.ib()
    method = attr.ib()
    enctype = attr.ib()
    encoding = attr.ib(default="utf-8")

    def lookupRenderMethod(self, name):
        """
        
        """
        raise MissingRenderMethod(name)


    @inlineCallbacks
    def render(self, request):
        """
        
        """
        session = yield self.procurer.procure_session()
        fields = list(self.form.all_fields()) + [
            Form.hidden(CSRF_PROTECTION,
                        session.identifier)
        ]
        field_tags = list(field.as_tags() for field in fields)
        returnValue(field_tags)



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
        for name, field in fields.items():
            field.maybe_named(name)
        self.fields = fields
        self.procurer_from_request = procurer_from_request


    def handler(self, route):
        """
        
        """
        def decorator(function):
            @route
            @inlineCallbacks
            def decorated(instance, request, *args, **kw):
                print("handling", request.args)
                procurer = _call(self.procurer_from_request,
                                 instance, request)
                session = yield procurer.procure_session()
                if session.mechanism == SessionMechanism.Cookie:
                    token = request.args.get(CSRF_PROTECTION)
                    if token != session.identifier:
                        raise CrossSiteRequestForgery()
                for field in self.fields.values():
                    kw[field.python_argument_name] = (
                        field.extract_from_request(request))
                returnValue(_call(function, instance, request, *args, **kw))
            decorated.__klein_bound__ = True
            return function
        return decorator


    def renderer(self, route, action, method="POST", enctype=form_data,
                 argument="form"):
        """
        
        """
        def decorator(function):
            @route
            @inlineCallbacks
            def decorated(instance, request, *args, **kw):
                procurer = yield self.procurer_from_request(request)
                form = FormRenderer(self, procurer, action, method, enctype)
                kw[argument] = form
                result = yield _call(function, request, *args, **kw)
                returnValue(result)
            decorated.__klein_bound__ = True
            return function
        return decorator


    def all_fields(self):
        """
        
        """
        any_submit = False
        for field in self.fields.values():
            yield field
            if field.form_input_type == "submit":
                any_submit = True
        if not any_submit:
            yield Field(str, form_input_type="submit",
                        python_argument_name="submit",
                        form_field_name="submit")

    @staticmethod
    def integer():
        """
        
        """
        return Field(coercer=int, form_input_type="number")


    @staticmethod
    def text():
        """
        
        """
        return Field(coercer=lambda x: unicode(x, "utf-8"),
                     form_input_type="text")


    @staticmethod
    def hidden(name, value):
        """
        
        """
        return Field(coercer=lambda x: unicode(x, "utf-8"),
                     form_input_type="hidden",
                     no_label=True,
                     value=value).maybe_named(name)

