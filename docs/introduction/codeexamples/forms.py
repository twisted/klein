from os import urandom
from binascii import hexlify

import attr
from attr import Factory

from zope.interface import implementer

from twisted.web.template import tags, slot
from twisted.python.components import Componentized
from twisted.internet.defer import succeed, fail

from klein import Klein, Plating, Form, SessionProcurer
from klein.interfaces import ISession, ISessionStore, NoSuchSession

app = Klein()

@implementer(ISession)
@attr.s
class MemorySession(object):
    """
    
    """
    identifier = attr.ib()
    is_confidential = attr.ib()
    authenticated_by = attr.ib()
    data = attr.ib(default=Factory(Componentized))


# XXX more of this needs to be provided by the framework; we should have
# built-in backends for a few databases; _especially_ users should not need to
# do their own session-ID generation unless they really want to
@implementer(ISessionStore)
class MemorySessionStore(object):
    """
    
    """

    def __init__(self):
        """
        
        """
        self._storage = {}

    def procurer(self):
        """
        
        """
        return SessionProcurer(self)

    def new_session(self, is_confidential, authenticated_by):
        """
        
        """
        identifier = hexlify(urandom(32))
        session = MemorySession(identifier, is_confidential, authenticated_by)
        self._storage[identifier] = session
        return succeed(session)

    def load_session(self, identifier, is_confidential, authenticated_by):
        """
        
        """
        if identifier in self._storage:
            result = self._storage[identifier]
            if is_confidential != result.is_confidential:
                self._storage.pop(identifier)
                return fail(NoSuchSession())
            return succeed(result)
        else:
            return fail(NoSuchSession())

    def sent_insecurely(self, tokens):
        """
        
        """


form = Form(
    dict(
        foo=Form.integer(minimum=3, maximum=10),
        bar=Form.text(),
    ),
    MemorySessionStore().procurer
)

style = Plating(tags=tags.html(
    tags.head(tags.title("yay")),
    tags.body(tags.div(slot(Plating.CONTENT))))
)


@style.routed(form.renderer(app.route("/my-form", methods=["GET"]),
                            action="/my-form?post=yes",
                            argument="the_form"),
              tags.div(slot("an_form")))
def form_renderer(request, the_form):
    return {"an_form": the_form}

@style.routed(form.handler(app.route("/my-form", methods=["POST"])),
              tags.h1('u did it: ', slot("an-form-arg")))
def post_handler(request, foo, bar):
    return {"an-form-arg": foo}

@style.routed(form.on_validation_failure_for(post_handler),
              [tags.h1('invalid form'),
               tags.div(slot('the-invalid-form'))])
def validation_failed(request, form):
    # handle validation failure; but how do I render the form?
    return {'the-invalid-form': form}


app.run("localhost", 8080)
