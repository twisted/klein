"""
Simple example of a public website.
"""


from foodwiki_config import requirer
from foodwiki_db import FoodRater
from foodwiki_templates import food, page, refresh

from twisted.web.template import slot, tags

from klein import Authorization, Field, FieldValues, Form, Klein, RenderableForm


app = Klein()


@requirer.require(
    page.routed(
        app.route("/rate-food", methods=["POST"]),
        tags.h1("Rated Food: ", slot("name")),
    ),
    name=Field.text(),
    rating=Field.number(minimum=1, maximum=5, kind=int),
    foodRater=Authorization(FoodRater),
)
async def postHandler(name: str, rating: int, foodRater: FoodRater) -> dict:
    await foodRater.rateFood(name, rating)
    return {
        "name": name,
        "rating": "\N{BLACK STAR}" * rating,
        "pageTitle": "Food Rated",
        "headExtras": refresh("/"),
    }


@requirer.require(
    page.routed(
        app.route("/", methods=["GET"]),
        tags.div(
            tags.ul(tags.li(render="foods:list")(slot("item"))),
            tags.div(slot("rateFoodForm")),
        ),
    ),
    ratingForm=Form.rendererFor(postHandler, action="/rate-food"),
    foodRater=Authorization(FoodRater),
)
async def frontPage(foodRater: FoodRater, ratingForm: RenderableForm) -> dict:
    allRatings = []
    async for eachFood in foodRater.allRatings():
        allRatings.append(
            food(name=eachFood.name, rating="\N{BLACK STAR}" * eachFood.rating)
        )
    return {"foods": allRatings, "rateFoodForm": ratingForm}


@requirer.require(
    page.routed(
        Form.onValidationFailureFor(postHandler),
        [tags.h1("invalid form"), tags.div(slot("the-invalid-form"))],
    ),
    renderer=Form.rendererFor(postHandler, action="/?post=again"),
)
def validationFailed(values: FieldValues, renderer: RenderableForm) -> dict:
    renderer.prevalidationValues = values.prevalidationValues
    renderer.validationErrors = values.validationErrors
    return {"the-invalid-form": renderer}


if __name__ == "__main__":
    from os.path import exists

    from foodwiki_config import DB_FILE, asyncDriver
    from foodwiki_db import applySchema

    from twisted.internet.defer import Deferred

    if not exists(DB_FILE):
        Deferred.fromCoroutine(applySchema(asyncDriver))

    app.run("localhost", 8080)
