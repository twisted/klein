
from twisted.web.template import tags, slot
from klein import Klein, Plating, Form, Field, Requirer, SessionProcurer
from klein.interfaces import ISession
from klein.storage.memory import MemorySessionStore

app = Klein()

sessions = MemorySessionStore()

requirer = Requirer()

@requirer.prerequisite([ISession])
def procurer(request):
    return SessionProcurer(sessions).procureSession(request)


style = Plating(tags=tags.html(
    tags.head(tags.title("yay")),
    tags.body(tags.div(slot(Plating.CONTENT))))
)

@style.routed(
    requirer.require(
        app.route("/", methods=["POST"]),
        foo=Field.integer(minimum=3, maximum=10), bar=Field.text(),
    ),
    tags.h1('u did it: ', slot("an-form-arg"))
)
def postHandler(request, foo, bar):
    return {"an-form-arg": foo}

@requirer.require(
    style.routed(
        app.route("/", methods=["GET"]),
        tags.div(slot("anForm"))
    ),
    theForm=Form.rendererFor(postHandler, action=u"/?post=yes")
)
def formRenderer(request, theForm):
    return {"anForm": theForm}

@requirer.require(
    style.routed(Form.onValidationFailureFor(postHandler),
                 [tags.h1('invalid form'),
                  tags.div(slot('the-invalid-form'))]),
    renderer=Form.rendererFor(postHandler, action=u"/?post=yes"),
)
def validationFailed(request, form, values, errors, renderer):
    renderer.prevalidationValues = values
    renderer.validationErrors = errors
    return {'the-invalid-form': renderer}


app.run("localhost", 8080)
