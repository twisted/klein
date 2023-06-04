"""
Simple example of a public website.
"""
import os
import sqlite3
from dataclasses import dataclass
from typing import AsyncIterable, Optional, Protocol

from twisted.internet.defer import Deferred, succeed
from twisted.web.iweb import IRequest
from twisted.web.template import Tag, slot, tags

from klein import (
    Authorization,
    Field,
    FieldValues,
    Form,
    Klein,
    Plating,
    RenderableForm,
    Requirer,
)
from klein.interfaces import (
    ISession,
    ISessionStore,
    ISimpleAccount,
    ISimpleAccountBinding,
)
from klein.storage.dbxs import accessor, many, query, statement
from klein.storage.dbxs.dbapi_async import (
    AsyncConnection,
    adaptSynchronousDriver,
    transaction,
)
from klein.storage.sql import (
    SQLSessionProcurer,
    applyBasicSchema,
    authorizerFor,
)


app = Klein()


asyncDriver = adaptSynchronousDriver(
    (lambda: sqlite3.connect("food-wiki.sqlite")), sqlite3.paramstyle
)

foodTable = """
CREATE TABLE food (
    name VARCHAR NOT NULL,
    rating INTEGER NOT NULL,
    account_id VARCHAR NOT NULL,
    FOREIGN KEY(account_id)
      REFERENCES account(account_id)
      ON DELETE CASCADE
)
"""


async def applySchema() -> None:
    await applyBasicSchema(asyncDriver)
    async with transaction(asyncDriver) as c:
        cur = await c.cursor()
        await cur.execute(foodTable)


@dataclass
class Food:
    txn: AsyncConnection
    name: str
    rating: int
    accountID: str


class FoodListSQL(Protocol):
    @query(
        sql="""
        select name, rating, account_id from food
        where account_id = {accountID}
        """,
        load=many(Food),
    )
    def getFoods(self, accountID: str) -> AsyncIterable[Food]:
        ...

    @statement(
        sql="insert into food (account_id, name, rating) values "
        "({accountID}, {name}, {rating})"
    )
    async def addFood(self, accountID: str, name: str, rating: int) -> None:
        ...


FoodListQueries = accessor(FoodListSQL)


@dataclass
class FoodList:
    account: ISimpleAccount
    db: FoodListSQL

    def foodsForUser(self) -> AsyncIterable[Food]:
        return self.db.getFoods(self.account.accountID)

    async def rateFood(self, name: str, rating: int) -> None:
        return await self.db.addFood(self.account.accountID, name, rating)


@authorizerFor(FoodList)
async def flub(
    store: ISessionStore, conn: AsyncConnection, session: ISession
) -> Optional[FoodList]:
    authd = await session.authorize([ISimpleAccountBinding])
    binding = authd[ISimpleAccountBinding]
    assert binding is not None
    accts = await binding.boundAccounts()
    if not accts:
        return None
    acct = accts[0]
    return FoodList(acct, FoodListQueries(conn))


if not os.path.exists("food-wiki.sqlite"):
    Deferred.fromCoroutine(applySchema())

sessions = SQLSessionProcurer(asyncDriver, [flub.authorizer])
requirer = Requirer()


@requirer.prerequisite([ISession])
def procurer(request: IRequest) -> Deferred[ISession]:
    result: Optional[ISession] = ISession(request, None)
    if result is not None:
        # TODO: onValidationFailureFor results in one require nested inside
        # another, which invokes this prerequisite twice. this mistake should
        # not be easy to make
        return succeed(result)
    return sessions.procureSession(request)


style = Plating(
    tags=tags.html(
        tags.head(
            tags.title("Foods Example: ", slot("pageTitle")),
            slot("headExtras"),
        ),
        tags.body(tags.div(slot(Plating.CONTENT))),
    ),
    defaults={"pageTitle": "Food List", "headExtras": ""},
    presentation_slots={"pageTitle", "headExtras", "addFoodForm", "loginForm"},
)

foodsList = [("test", 1)]


def refresh(url: str) -> Tag:
    return tags.meta(content=f"0;URL='{url}'", **{"http-equiv": "refresh"})


@requirer.require(
    style.routed(
        app.route("/", methods=["POST"]),
        tags.h1("Added Food: ", slot("name")),
    ),
    name=Field.text(),
    rating=Field.number(minimum=1, maximum=5, kind=int),
    foodList=Authorization(FoodList),
)
async def postHandler(name: str, rating: int, foodList: FoodList) -> dict:
    await foodList.rateFood(name, rating)
    return {
        "name": name,
        "rating": "\N{BLACK STAR}" * rating,
        "pageTitle": "Food Added",
        "headExtras": refresh("/"),
    }


@requirer.require(
    style.routed(
        app.route("/login", methods=["POST"]),
        tags.div(tags.h1("logged in", slot("didlogin"))),
    ),
    username=Field.text(),
    password=Field.password(),
    binding=Authorization(ISimpleAccountBinding),
)
async def login(
    username: str, password: str, binding: ISimpleAccountBinding
) -> dict:
    await binding.bindIfCredentialsMatch(username, password)
    return {
        "didlogin": "yes",
        "headExtras": refresh("/"),
    }


@requirer.require(
    style.routed(
        app.route("/logout", methods=["POST"]),
        tags.div(tags.h1("logged out ", slot("didlogout"))),
    ),
    binding=Authorization(ISimpleAccountBinding),
    ignored=Field.submit("log out"),
)
async def logout(
    binding: ISimpleAccountBinding,
    ignored: str,
) -> dict:
    await binding.unbindThisSession()
    return {"didlogout": "yes", "headExtras": refresh("/")}


@requirer.require(
    style.routed(
        app.route("/login", methods=["GET"]),
        tags.div("form", slot("form")),
    ),
    theForm=Form.rendererFor(login, action="/login"),
)
async def showLogin(theForm: object) -> dict:
    return {"form": theForm}


@requirer.require(
    style.routed(
        app.route("/signup", methods=["POST"]),
        tags.h1("signed up", slot("signedUp")),
    ),
    username=Field.text(),
    password=Field.password(),
    password2=Field.password(),
    binding=Authorization(ISimpleAccountBinding),
)
async def signup(
    username: str, password: str, password2: str, binding: ISimpleAccountBinding
) -> dict:
    await binding.createAccount(username, "", password)
    return {"signedUp": "yep", "headExtras": refresh("/login")}


@requirer.require(
    style.routed(
        app.route("/signup", methods=["GET"]),
        tags.div(tags.h1("sign up pls"), slot("signupForm")),
    ),
    binding=Authorization(ISimpleAccountBinding),
    theForm=Form.rendererFor(signup, action="/signup"),
)
async def showSignup(
    binding: ISimpleAccountBinding,
    theForm: RenderableForm,
) -> dict:
    return {"signupForm": theForm}


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
            tags.div(slot("loginForm")),
        ),
    ),
    theForm=Form.rendererFor(postHandler, action="/?post=yes"),
    loginForm=Form.rendererFor(login, action="/login"),
    logoutForm=Form.rendererFor(logout, action="/logout"),
    foodList=Authorization(FoodList, required=False),
)
async def formRenderer(
    theForm: RenderableForm,
    loginForm: RenderableForm,
    logoutForm: RenderableForm,
    foodList: Optional[FoodList],
) -> dict:
    result = []
    if foodList is not None:
        async for eachFood in foodList.foodsForUser():
            result.append(eachFood)
    return {
        "addFoodForm": theForm if (foodList is not None) else "",
        "loginForm": loginForm if (foodList is None) else logoutForm,
        "foods": [
            food(name=each.name, rating="\N{BLACK STAR}" * each.rating)
            for each in result
        ],
    }


@requirer.require(
    style.routed(
        Form.onValidationFailureFor(postHandler),
        [tags.h1("invalid form"), tags.div(slot("the-invalid-form"))],
    ),
    renderer=Form.rendererFor(postHandler, action="/?post=yes"),
)
def validationFailed(values: FieldValues, renderer: RenderableForm) -> dict:
    renderer.prevalidationValues = values.prevalidationValues
    renderer.validationErrors = values.validationErrors
    return {"the-invalid-form": renderer}


app.run("localhost", 8080)
