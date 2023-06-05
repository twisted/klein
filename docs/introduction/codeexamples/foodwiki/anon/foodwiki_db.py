from dataclasses import dataclass
from typing import AsyncIterable, Optional, Protocol

from klein.interfaces import ISession, ISessionStore
from klein.storage.dbxs import accessor, many, query, statement
from klein.storage.dbxs.dbapi_async import (
    AsyncConnectable,
    AsyncConnection,
    transaction,
)
from klein.storage.sql import applyBasicSchema, authorizerFor


foodTable = """
CREATE TABLE food (
    name VARCHAR NOT NULL,
    rating INTEGER NOT NULL
)
"""


async def applySchema(connectable: AsyncConnectable) -> None:
    await applyBasicSchema(connectable)
    async with transaction(connectable) as c:
        cur = await c.cursor()
        await cur.execute(foodTable)


@dataclass
class FoodRating:
    txn: AsyncConnection
    name: str
    rating: int


class RatingsDB(Protocol):
    @query(
        sql="select name, rating from food",
        load=many(FoodRating),
    )
    def allRatings(self) -> AsyncIterable[FoodRating]:
        ...

    @statement(sql="insert into food (name, rating) values ({name}, {rating})")
    async def addRating(self, name: str, rating: int) -> None:
        ...


accessRatings = accessor(RatingsDB)


@dataclass
class FoodRater:
    db: RatingsDB

    def allRatings(self) -> AsyncIterable[FoodRating]:
        return self.db.allRatings()

    async def rateFood(self, name: str, rating: int) -> None:
        return await self.db.addRating(name, rating)


@authorizerFor(FoodRater)
async def authorizeFoodList(
    store: ISessionStore, conn: AsyncConnection, session: ISession
) -> Optional[FoodRater]:
    return FoodRater(accessRatings(conn))


allAuthorizers = [authorizeFoodList.authorizer]
