# -*- test-case-name: klein.storage.sql.test.test_transactions -*-
from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Awaitable, Callable, Dict

from attrs import Factory, define, field
from zope.interface import Interface, implementer

from twisted.internet.defer import Deferred, gatherResults
from twisted.logger import Logger
from twisted.python.components import Componentized, registerAdapter
from twisted.web.iweb import IRequest
from twisted.web.server import Request

from klein.interfaces import (
    IDependencyInjector,
    IRequestLifecycle,
    IRequiredParameter,
)

from ..._util import eagerDeferredCoroutine
from ...interfaces import IRequirementContext
from ..dbxs.dbapi_async import AsyncConnectable, AsyncConnection


log = Logger()


class ITransactionRequestAssociator(Interface):
    """
    Request component which associates transactions with requests.
    """

    def transactionForConnectable(
        connectable: AsyncConnectable,
    ) -> Deferred[AsyncConnection]:
        """
        Get the open database transaction for the given engine.
        """


@implementer(ITransactionRequestAssociator)
@define
class TransactionRequestAssociator:
    """
    Associate a transaction with a request.
    """

    request: Request
    map: Dict[AsyncConnectable, AsyncConnection] = field(default=Factory(dict))
    waitMap: Dict[AsyncConnectable, Awaitable[None]] = field(
        default=Factory(dict)
    )
    attached: bool = False

    @eagerDeferredCoroutine
    async def transactionForConnectable(
        self, connectable: AsyncConnectable
    ) -> AsyncConnection:
        """
        Retrieve a transaction from the async connection.
        """
        if connectable in self.waitMap:
            await self.waitMap[connectable]
        if connectable in self.map:
            return self.map[connectable]
        reqctx = IRequirementContext(self.request)
        waiter = self.waitMap[connectable] = Deferred()
        await reqctx.enter_async_context(self.transactify())
        cxn = await connectable.connect()
        self.map[connectable] = cxn
        del self.waitMap[connectable]
        waiter.callback(None)
        return cxn

    @asynccontextmanager
    async def transactify(self) -> AsyncIterator[None]:
        """
        Commit all associated transactions.

        @param ignored: To be usable as a Deferred callback, accept an
            argument, but discard it.
        """
        print("start")
        try:
            yield
        finally:
            # Break cycle, allow for sub-transactions later (i.e. in renderers)
            print("dissociating")
            self.request.unsetComponent(ITransactionRequestAssociator)
            await gatherResults(
                [
                    Deferred.fromCoroutine(value.commit())
                    for value in self.map.values()
                ]
            )


@implementer(IRequiredParameter, IDependencyInjector)
@dataclass
class Transaction:
    """
    Require a transaction from a specified connectable.

    Example::

        @dataclass
        class Application:
            connectable: AsyncConnectable

            router: ClassVar[Klein] = Klein()
            requirer: ClassVar[Requirer] = Requirer()

            def _db(self) -> AsyncConnectable:
                return self.connectable

            @requirer.require(router.route("/page"),
                              txn=Transaction(_db))
            async def page(self, txn: AsyncConnection):
                return (await (await txn.cursor())
                        .execute("select * from rows"))

    """

    getConnectable: Callable[[Any], AsyncConnectable]

    def registerInjector(
        self,
        injectionComponents: Componentized,
        parameterName: str,
        lifecycle: IRequestLifecycle,
    ) -> IDependencyInjector:
        """
        I am a dependency injector.
        """
        return self

    async def injectValue(
        self,
        instance: object,
        request: IRequest,
        routeParams: Dict[str, object],
    ) -> AsyncConnection:
        """
        Get a transaction from the associated connectable.
        """
        associator = ITransactionRequestAssociator(request)
        connector = self.getConnectable(instance)
        return await associator.transactionForConnectable(connector)

    def finalize(self) -> None:
        """
        Finalize parameter injection setup.
        """


registerAdapter(
    TransactionRequestAssociator, IRequest, ITransactionRequestAssociator
)


async def requestBoundTransaction(
    request: IRequest, connectable: AsyncConnectable
) -> AsyncConnection:
    """
    Retrieve a transaction that is bound to the lifecycle of the given request.

    There are three use-cases for this lifecycle:

        1. 'normal CRUD' - a request begins, a transaction is associated with
           it, and the transaction completes when the request completes.  The
           appropriate time to commit the transaction is the moment before the
           first byte goes out to the client.  The appropriate moment to
           interpose this commit is in , since the
           HTTP status code should be an indicator of whether the transaction
           succeeded or failed.

        2. 'just the session please' - a request begins, a transaction is
           associated with it in order to discover the session, and the
           application code in question isn't actually using the database.
           (Ideally as expressed through "the dependency-declaration decorator,
           such as @authorized, did not indicate that a transaction will be
           required").

        3. 'fancy API stuff' - a request begins, a transaction is associated
           with it in order to discover the session, the application code needs
           to then do I{something} with that transaction in-line with the
           session discovery, but then needs to commit in order to relinquish
           all database locks while doing some potentially slow external API
           calls, then start a I{new} transaction later in the request flow.
    """
    return await ITransactionRequestAssociator(
        request
    ).transactionForConnectable(connectable)
