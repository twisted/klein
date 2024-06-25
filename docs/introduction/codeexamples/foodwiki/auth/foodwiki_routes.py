"""
Simple example of a public website.
"""


from typing import Optional, Union

from foodwiki_config import app, requirer
from foodwiki_db import FoodCritic, RatingsViewer
from foodwiki_templates import food, linkedFood, page, refresh

from twisted.web.template import Tag, slot, tags

from klein import (
    Authorization,
    Field,
    FieldValues,
    Form,
    Plating,
    RenderableForm,
)
from klein.interfaces import ISimpleAccount


@page.widgeted
def notLoggedIn() -> dict:
    return {Plating.CONTENT: "You are not logged in."}


@requirer.require(
    page.routed(
        app.route("/rate-food", methods=["POST"]),
        tags.h1("Rated Food: ", slot("name")),
    ),
    name=Field.text(),
    rating=Field.number(minimum=1, maximum=5, kind=int),
    critic=Authorization(
        FoodCritic, whenDenied=lambda interface, instance: notLoggedIn.widget()
    ),
)
async def postHandler(name: str, rating: int, critic: FoodCritic) -> dict:
    await critic.rateFood(name, rating)
    return {
        "name": name,
        "rating": "\N{BLACK STAR}" * rating,
        "pageTitle": "Food Rated",
        "headExtras": refresh("/"),
    }


rateFoodForm = Form.rendererFor(postHandler, action="/rate-food")


@requirer.require(
    page.routed(
        app.route("/", methods=["GET"]),
        tags.div(
            tags.ul(tags.li(render="foods:list")(slot("item"))),
            tags.div(slot("rateFoodForm")),
        ),
    ),
    ratingForm=rateFoodForm,
    critic=Authorization(FoodCritic, required=False),
    viewer=Authorization(RatingsViewer),
)
async def frontPage(
    ratingForm: RenderableForm,
    critic: Optional[FoodCritic],
    viewer: RatingsViewer,
) -> dict:
    allRatings = []
    async for eachFood in viewer.topRatings():
        allRatings.append(
            linkedFood(
                name=eachFood.name,
                rating="\N{BLACK STAR}" * eachFood.rating,
                username=eachFood.username,
            )
        )
    return {
        "foods": allRatings,
        "rateFoodForm": "" if critic is None else ratingForm,
        "pageTitle": "top-rated foods",
    }


@requirer.require(
    page.routed(
        app.route("/users/<string:username>", methods=["GET"]),
        tags.div(
            tags.ul(tags.li(render="userRatings:list")(slot("item"))),
        ),
    ),
    viewer=Authorization(RatingsViewer),
)
async def userPage(viewer: RatingsViewer, username: str) -> dict:
    userRatings = []
    async for eachFood in viewer.ratingsByUserName(username):
        userRatings.append(
            food(name=eachFood.name, rating="\N{BLACK STAR}" * eachFood.rating)
        )
    return {
        "userRatings": userRatings,
        "pageTitle": f"ratings by {username}",
    }


@requirer.require(
    page.renderMethod, critic=Authorization(ISimpleAccount, required=False)
)
def whenLoggedIn(tag: Tag, critic: Optional[ISimpleAccount]) -> Union[Tag, str]:
    return "" if critic is None else tag


@requirer.require(
    page.renderMethod, critic=Authorization(FoodCritic, required=False)
)
def whenLoggedOut(
    tag: Tag, critic: Optional[ISimpleAccount]
) -> Union[Tag, str]:
    return "" if critic is not None else tag


@requirer.require(
    page.routed(
        Form.onValidationFailureFor(postHandler),
        [tags.h1("invalid form"), tags.div(slot("the-invalid-form"))],
    ),
    renderer=rateFoodForm,
)
def validationFailed(values: FieldValues, renderer: RenderableForm) -> dict:
    renderer.prevalidationValues = values.prevalidationValues
    renderer.validationErrors = values.validationErrors
    return {"the-invalid-form": renderer}


if __name__ == "__main__":
    from os.path import exists

    from foodwiki_config import DB_FILE, asyncDriver
    from foodwiki_db import applySchema

    # load other routes for side-effects of gathering them into the app object.
    __import__("foodwiki_auth_routes")

    from twisted.internet.defer import Deferred

    if not exists(DB_FILE):
        Deferred.fromCoroutine(applySchema(asyncDriver))

    app.run("localhost", 8080)
