from dataclasses import dataclass
from typing import Any, AsyncIterable, Optional, Protocol, Sequence

from klein.interfaces import (
    ISession,
    ISessionStore,
    ISimpleAccount,
    ISimpleAccountBinding,
    SessionMechanism,
)
from klein.storage.dbxs import accessor, many, query, statement
from klein.storage.dbxs.dbapi_async import (
    AsyncConnectable,
    AsyncConnection,
    transaction,
)
from klein.storage.sql import applyBasicSchema, authorizerFor
from klein.storage.sql._sql_glue import SQLAuthorizer


foodTable = """
CREATE TABLE food (
    name VARCHAR NOT NULL,
    rating INTEGER NOT NULL,
    rated_by VARCHAR NOT NULL,
    FOREIGN KEY(rated_by)
      REFERENCES account(account_id)
      ON DELETE CASCADE
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
    ratedByAccountID: str


@dataclass
class NamedRating:
    txn: AsyncConnection
    name: str
    rating: int
    username: str


class PublicRatingsDB(Protocol):
    @query(
        sql="""
        select name, rating, rated_by from food
            join account on(food.rated_by = account.account_id)
            where account.username = {userName}
        """,
        load=many(FoodRating),
    )
    def ratingsByUserName(self, userName: str) -> AsyncIterable[FoodRating]:
        ...

    @query(
        sql="""
        select name, rating, account.username from food
            join account on(food.rated_by = account.account_id)
            order by rating desc
            limit 10
        """,
        load=many(NamedRating),
    )
    def topRatings(self) -> AsyncIterable[NamedRating]:
        ...


accessPublicRatings = accessor(PublicRatingsDB)


@dataclass
class RatingsViewer:
    db: PublicRatingsDB

    def ratingsByUserName(self, userName: str) -> AsyncIterable[FoodRating]:
        return self.db.ratingsByUserName(userName)

    def topRatings(self) -> AsyncIterable[NamedRating]:
        return self.db.topRatings()


@authorizerFor(RatingsViewer)
async def authorizeRatingsViewer(
    store: ISessionStore, conn: AsyncConnection, session: ISession
) -> RatingsViewer:
    return RatingsViewer(accessPublicRatings(conn))


class RatingsDB(Protocol):
    @query(
        sql="select name, rating, rated_by from food"
        "where rated_by = {accountID}",
        load=many(FoodRating),
    )
    def ratingsByUserID(self, accountID: str) -> AsyncIterable[FoodRating]:
        ...

    @statement(
        sql="""
        insert into food (rated_by, name, rating)
        values ({accountID}, {name}, {rating})
        """
    )
    async def addRating(self, accountID: str, name: str, rating: int) -> None:
        ...


accessRatings = accessor(RatingsDB)


@dataclass
class FoodCritic:
    db: RatingsDB
    account: ISimpleAccount

    def myRatings(self) -> AsyncIterable[FoodRating]:
        return self.db.ratingsByUserID(self.account.accountID)

    async def rateFood(self, name: str, rating: int) -> None:
        return await self.db.addRating(self.account.accountID, name, rating)


@authorizerFor(FoodCritic)
async def authorizeFoodCritic(
    store: ISessionStore, conn: AsyncConnection, session: ISession
) -> Optional[FoodCritic]:
    accts = await (await session.authorize([ISimpleAccountBinding]))[
        ISimpleAccountBinding
    ].boundAccounts()
    if not accts:
        return None
    return FoodCritic(accessRatings(conn), accts[0])


@dataclass
class APIKeyProvisioner:
    sessionStore: ISessionStore
    session: ISession
    account: ISimpleAccount

    async def provisionAPIKey(self) -> str:
        """
        Provision a new API key for the given account.
        """
        apiKeySession = await self.sessionStore.newSession(
            self.session.isConfidential, SessionMechanism.Header
        )
        await self.account.bindSession(apiKeySession)
        return apiKeySession.identifier


@authorizerFor(APIKeyProvisioner)
async def authorizeProvisioner(
    store: ISessionStore, conn: AsyncConnection, session: ISession
) -> Optional[APIKeyProvisioner]:
    accts = await (await session.authorize([ISimpleAccountBinding]))[
        ISimpleAccountBinding
    ].boundAccounts()
    if not accts:
        return None
    return APIKeyProvisioner(store, session, accts[0])


allAuthorizers: Sequence[SQLAuthorizer[Any]] = [
    authorizeFoodCritic.authorizer,
    authorizeRatingsViewer.authorizer,
    authorizeProvisioner.authorizer,
]
