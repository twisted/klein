"""
Simple example of a public website.
"""
from twisted.web.template import Tag, slot, tags

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
        tags.head(
            tags.title("Foods Example: ", slot("pageTitle")),
            slot("headExtras"),
        ),
        tags.body(tags.div(slot(Plating.CONTENT))),
    ),
    defaults={"pageTitle": "Food List", "headExtras": ""},
    presentation_slots={"pageTitle", "headExtras", "addFoodForm"},
)

foodsList = [("test", 1)]


@requirer.require(
    style.routed(
        app.route("/", methods=["POST"]),
        tags.h1("Added Food: ", slot("name")),
    ),
    name=Field.text(),
    rating=Field.number(minimum=1, maximum=5, kind=int),
)
def postHandler(name, rating):
    foodsList.append((name, rating))
    return {
        "name": name,
        "rating": "\N{BLACK STAR}" * rating,
        "pageTitle": "Food Added",
        "headExtras": tags.meta(
            content="0;URL='/'", **{"http-equiv": "refresh"}
        ),
    }


@Plating.fragment
def food(name: str, rating: str) -> Tag:
    return tags.div(
        tags.div("food:", name),
        tags.div("rating:", rating),
    )


@requirer.require(
    style.routed(
        app.route("/", methods=["GET"]),
        tags.div(
            tags.ul(tags.li(render="foods:list")(slot("item"))),
            tags.div(slot("addFoodForm")),
        ),
    ),
    theForm=Form.rendererFor(postHandler, action="/?post=yes"),
)
def formRenderer(theForm):
    global foodsList
    return {
        "addFoodForm": theForm,
        "foods": [
            food(name=name, rating="\N{BLACK STAR}" * rating)
            for name, rating in foodsList
        ],
    }


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
