from os import urandom
from binascii import hexlify

import attr
from attr import Factory

from zope.interface import implementer

from twisted.web.template import tags, slot
from twisted.python.components import Componentized
from twisted.internet.defer import succeed, fail

from klein import Klein, Plating, form, SessionProcurer
from klein.interfaces import ISession, ISessionStore, NoSuchSession

app = Klein()

@implementer(ISession)
@attr.s
class MemorySession(object):
    """
    
    """
    identifier = attr.ib()
    isConfidential = attr.ib()
    authenticatedBy = attr.ib()
    data = attr.ib(default=Factory(Componentized))


# XXX more of this needs to be provided by the framework; we should have
# built-in backends for a few databases; _especially_ users should not need to
# do their own session-ID generation unless they really want to
@implementer(ISessionStore)
class MemorySessionStore(object):
    def __init__(self):
        self._storage = {}

    def procurer(self):
        return SessionProcurer(self)

    def newSession(self, isConfidential, authenticatedBy):
        identifier = hexlify(urandom(32)).decode('ascii')
        session = MemorySession(identifier, isConfidential, authenticatedBy)
        self._storage[identifier] = session
        return succeed(session)

    def loadSession(self, identifier, isConfidential, authenticatedBy):
        if identifier in self._storage:
            result = self._storage[identifier]
            if isConfidential != result.isConfidential:
                self._storage.pop(identifier)
                return fail(NoSuchSession())
            return succeed(result)
        else:
            return fail(NoSuchSession())

    def sent_insecurely(self, tokens):
        return

sessions = MemorySessionStore()

sample = form(
    foo=form.integer(minimum=3, maximum=10),
    bar=form.text(),
)

style = Plating(tags=tags.html(
    tags.head(tags.title("yay")),
    tags.body(tags.div(slot(Plating.CONTENT))))
)


@style.routed(sample.renderer(sessions.procurer,
                              app.route("/my-form", methods=["GET"]),
                              action="/my-form?post=yes",
                              argument="the_form"),
              tags.div(slot("an_form")))
def form_renderer(request, the_form):
    return {"an_form": the_form}

@style.routed(sample.handler(sessions.procurer,
                           app.route("/my-form", methods=["POST"])),
              tags.h1('u did it: ', slot("an-form-arg")))
def post_handler(request, foo, bar):
    return {"an-form-arg": foo}

@style.routed(sample.on_validation_failure_for(post_handler),
              [tags.h1('invalid form'),
               tags.div(slot('the-invalid-form'))])
def validation_failed(request, form):
    return {'the-invalid-form': form}


app.run("localhost", 8080)
