
from twisted.web.template import tags, slot
from klein import Klein, Plating, form, SessionProcurer
from klein.storage.memory import MemorySessionStore

from klein._session import requirer

app = Klein()

sessions = MemorySessionStore()

@requirer
def authorizer():
    return SessionProcurer(sessions)

sample = form(
    foo=form.integer(minimum=3, maximum=10),
    bar=form.text(),
).authorizedUsing(authorizer)

style = Plating(tags=tags.html(
    tags.head(tags.title("yay")),
    tags.body(tags.div(slot(Plating.CONTENT))))
)


@style.routed(sample.renderer(app.route("/my-form", methods=["GET"]),
                              action="/my-form?post=yes",
                              argument="the_form"),
              tags.div(slot("an_form")))
def form_renderer(request, the_form):
    return {"an_form": the_form}

@style.routed(sample.handler(app.route("/my-form", methods=["POST"])),
              tags.h1('u did it: ', slot("an-form-arg")))
def post_handler(request, foo, bar):
    return {"an-form-arg": foo}

@style.routed(sample.onValidationFailureFor(post_handler),
              [tags.h1('invalid form'),
               tags.div(slot('the-invalid-form'))])
def validation_failed(request, form):
    return {'the-invalid-form': form}


app.run("localhost", 8080)
