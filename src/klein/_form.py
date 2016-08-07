
import attr

from zope.interface import implementer

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.template import tags, MissingRenderMethod
from twisted.web.iweb import IRenderable

from klein.interfaces import ISessionProcurer

@attr.s
class Field(object):
    """
    
    """
    coercer = attr.ib()
    form_input_type = attr.ib()
    python_argument_name = attr.ib(default=None)
    form_field_name = attr.ib(default=None)
    form_label = attr.ib(default=None)

    def maybe_named(self, name):
        """
        
        """
        if self.python_argument_name is None:
            self.python_argument_name = name
        if self.form_field_name is None:
            self.form_field_name = name
        if self.form_label is None:
            self.form_label = name.capitalize()

    def as_tags(self):
        """
        
        """
        return tags.label(self.form_label, ": ",
                          tags.input(type=self.form_input_type,
                          name=self.form_field_name))


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
    action = attr.ib()
    enctype = attr.ib()
    method = attr.ib()
    encoding = attr.ib(default="utf-8")

    def lookupRenderMethod(self, name):
        """
        
        """
        raise MissingRenderMethod(name)


    @inlineCallbacks
    def render(self, request):
        """
        
        """
        access = ISessionProcurer(request, None)
        if access is None:
            raise ValueError("useful message about how to configure session")
        session = yield access.procure_session()
        fields = list(self.form.all_fields()) + [Form.hidden(session.uid)]
        field_tags = list(field.as_tags() for field in fields)
        returnValue(field_tags)


@attr.s(init=False)
class Form(object):
    """
    
    """
    fields = attr.ib()

    form_data = b'multipart/form-data'
    url_encoded = b'application/x-www-form-urlencoded'

    def __init__(self, fields):
        """
        
        """
        for name, field in fields.items():
            field.maybe_named(name)
        self.fields = fields


    def handler(self, route):
        """
        
        """
        def decorator(function):
            def decorated(request, *args, **kw):
                print("handling", request.args)
                for field in self.fields.values():
                    kw[field.python_argument_name] = (
                        field.extract_from_request(request))
                return function(request, *args, **kw)
            route(decorated)
            return function
        return decorator


    def renderer(self, action, method="POST", enctype=form_data):
        """
        
        """
        return FormRenderer(self, action, method, enctype, "utf-8")

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

