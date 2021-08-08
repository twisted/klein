from twisted.web.template import slot, tags

from klein import Field, Form, Klein, Plating, Requirer, SessionProcurer
from klein.interfaces import ISession
from klein.storage.memory import MemorySessionStore


app = Klein()

sessions = MemorySessionStore()

requirer = Requirer()


@requirer.prerequisite([ISession])
def procurer(request):
    return SessionProcurer(sessions).procureSession(request)


style = Plating(
    tags=tags.html(
        tags.head(tags.title("yay")), tags.body(tags.div(slot(Plating.CONTENT)))
    )
)


@requirer.require(
    style.routed(
        app.route("/", methods=["POST"]),
        tags.h1("u did it: ", slot("an-form-arg")),
    ),
    foo=Field.number(minimum=3, maximum=10),
    bar=Field.text(),
)
def postHandler(foo, bar):
    return {"an-form-arg": foo}


@requirer.require(
    style.routed(app.route("/", methods=["GET"]), tags.div(slot("anForm"))),
    theForm=Form.rendererFor(postHandler, action="/?post=yes"),
)
def formRenderer(theForm):
    return {"anForm": theForm}


@requirer.require(
    style.routed(
        Form.onValidationFailureFor(postHandler),
        [tags.h1("invalid form"), tags.div(slot("the-invalid-form"))],
    ),
    renderer=Form.rendererFor(postHandler, action="/?post=yes"),
)
def validationFailed(values, renderer):
    renderer.prevalidationValues = values.prevalidationValues
    renderer.validationErrors = values.validationErrors
    return {"the-invalid-form": renderer}


app.run("localhost", 8080)
