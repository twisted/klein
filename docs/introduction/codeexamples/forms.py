from zope.interface import implementer

from twisted.web.template import tags, slot

from klein import Klein, Plating, Form, SessionProcurer
from klein.interfaces import ISessionStore

app = Klein()

@implementer(ISessionStore)
class MemorySessionStore(object):
    """
    
    """

    def procurer(self, request):
        """
        
        """
        return SessionProcurer(self, request)


form = Form(
    dict(
        foo=Form.integer(),
        bar=Form.text(),
    ),
    MemorySessionStore().procurer
)

style = Plating(tags=tags.html(
    tags.head(tags.title("yay")),
    tags.body(tags.div(slot(Plating.CONTENT))))
)

@form.handler(style.routed(app.route("/my-form", methods=["POST"]),
                           tags.h1('u did it',
                                   slot("an-form-arg"))))
def post_handler(request, foo, bar):
    return {
        "an-form-arg": foo,
    }

@form.renderer(style.routed(app.route("/my-form", methods=["GET"]),
                            tags.div(slot("an_form"))),
               action="/my-form?post=yes",
               argument="the_form")
def form_renderer(request, the_form):
    return {"an_form": the_form}


app.run("localhost", 8080)
