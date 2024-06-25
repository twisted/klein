# -*- test-case-name: klein.storage.dbxs.test.test_sync_adapter -*-
"""
Async version of db-api methods which associate each underlying db-api
connection with a specific thread, since some database drivers have issues with
sharing connections and cursors between threads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from queue import Queue
from threading import Thread
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    List,
    Mapping,
    Optional,
    Sequence,
    Type,
    TypeVar,
)

from twisted._threads import AlreadyQuit, ThreadWorker
from twisted._threads._ithreads import IExclusiveWorker
from twisted.internet.defer import Deferred
from twisted.python.failure import Failure

from ._dbapi_async_protocols import (
    AsyncConnectable,
    AsyncConnection,
    AsyncCursor,
    ParamStyle,
)
from ._dbapi_types import DBAPIColumnDescription, DBAPIConnection, DBAPICursor


_T = TypeVar("_T")

F = Callable[[], None]


class InvalidConnection(Exception):
    """
    The connection has already been closed, or the transaction has already been
    committed.
    """


def _newThread() -> IExclusiveWorker:
    def _startThread(target: Callable[[], None]) -> Thread:
        thread = Thread(target=target, daemon=True)
        thread.start()
        return thread

    return ThreadWorker(_startThread, Queue())


@dataclass
class ExclusiveWorkQueue:
    _worker: Optional[IExclusiveWorker]
    _deliver: Callable[[F], None]

    def worker(self, invalidate: bool = False) -> IExclusiveWorker:
        """
        Assert that the worker should still be present, then return it
        (invalidating it if the flag is passed).
        """
        if invalidate:
            w, self._worker = self._worker, None
        else:
            w = self._worker
        if w is None:
            raise AlreadyQuit("cannot quit twice")
        return w

    def perform(
        self,
        work: Callable[[], _T],
    ) -> Deferred[_T]:
        """
        Perform the given work on the underlying thread, delivering the result
        back to the main thread with L{ExclusiveWorkQueue._deliver}.
        """

        deferred: Deferred[_T] = Deferred()

        def workInThread() -> None:
            try:
                result = work()
            except BaseException:
                f = Failure()
                self._deliver(lambda: deferred.errback(f))
            else:
                self._deliver(lambda: deferred.callback(result))

        self.worker().do(workInThread)

        return deferred

    def quit(self) -> None:
        """
        Allow this thread to stop, and invalidate this L{ExclusiveWorkQueue} by
        removing its C{_worker} attribute.
        """
        self.worker(True).quit()

    def __del__(self) -> None:
        """
        When garbage collected make sure we kill off our underlying thread.
        """
        if self._worker is None:
            return
        # might be nice to emit a ResourceWarning here, since __del__ is not a
        # good way to clean up resources.
        self.quit()


@dataclass
class ThreadedCursorAdapter(AsyncCursor):
    """
    A cursor that can be interacted with asynchronously.
    """

    _cursor: DBAPICursor
    _exclusive: ExclusiveWorkQueue

    async def description(self) -> Optional[Sequence[DBAPIColumnDescription]]:
        return await self._exclusive.perform(lambda: self._cursor.description)

    async def rowcount(self) -> int:
        return await self._exclusive.perform(lambda: self._cursor.rowcount)

    async def fetchone(self) -> Optional[Sequence[Any]]:
        return await self._exclusive.perform(self._cursor.fetchone)

    async def fetchmany(
        self, size: Optional[int] = None
    ) -> Sequence[Sequence[Any]]:
        a = [size] if size is not None else []
        return await self._exclusive.perform(lambda: self._cursor.fetchmany(*a))

    async def fetchall(self) -> Sequence[Sequence[Any]]:
        return await self._exclusive.perform(self._cursor.fetchall)

    async def execute(
        self,
        operation: str,
        parameters: Sequence[Any] | Mapping[str, Any] = (),
    ) -> object:
        """
        Execute the given statement.
        """

        def query() -> object:
            return self._cursor.execute(operation, parameters)

        return await self._exclusive.perform(query)

    async def executemany(
        self, __operation: str, __seq_of_parameters: Sequence[Sequence[Any]]
    ) -> object:
        def query() -> object:
            return self._cursor.executemany(__operation, __seq_of_parameters)

        return await self._exclusive.perform(query)

    async def close(self) -> None:
        """
        Close the underlying cursor.
        """
        await self._exclusive.perform(self._cursor.close)


@dataclass
class ThreadedConnectionAdapter:
    """
    Asynchronous database connection that binds to a specific thread.
    """

    _connection: Optional[DBAPIConnection]
    _exclusive: ExclusiveWorkQueue
    paramstyle: ParamStyle

    def _getConnection(self, invalidate: bool = False) -> DBAPIConnection:
        """
        Get the connection, raising an exception if it's already been
        invalidated.
        """
        c = self._connection
        assert (
            c is not None
        ), "should not be able to get a bad connection via public API"
        if invalidate:
            self._connection = None
        return c

    async def close(self) -> None:
        """
        Close the connection if it hasn't been closed yet.
        """
        connection = self._getConnection(True)
        await self._exclusive.perform(connection.close)
        self._exclusive.quit()

    async def cursor(self) -> ThreadedCursorAdapter:
        """
        Construct a new async cursor.
        """
        c = self._getConnection()
        cur = await self._exclusive.perform(c.cursor)
        return ThreadedCursorAdapter(cur, self._exclusive)

    async def rollback(self) -> None:
        """
        Roll back the current transaction.
        """
        c = self._getConnection()
        await self._exclusive.perform(c.rollback)

    async def commit(self) -> None:
        """
        Roll back the current transaction.
        """
        c = self._getConnection()
        await self._exclusive.perform(c.commit)


@dataclass(eq=False)
class PooledThreadedConnectionAdapter:
    """
    Pooled connection adapter that re-adds itself back to the pool upon commit
    or rollback.
    """

    _adapter: Optional[ThreadedConnectionAdapter]
    _pool: ThreadedConnectionPool
    _cursors: List[ThreadedCursorAdapter]

    def _original(self, invalidate: bool) -> ThreadedConnectionAdapter:
        """
        Check for validity, return the underlying connection, and then
        optionally invalidate this adapter.
        """
        a = self._adapter
        if a is None:
            raise InvalidConnection("The connection has already been closed.")
        if invalidate:
            self._adapter = None
        return a

    @property
    def paramstyle(self) -> str:
        return self._original(False).paramstyle

    async def cursor(self) -> ThreadedCursorAdapter:
        it = await self._original(False).cursor()
        self._cursors.append(it)
        return it

    async def rollback(self) -> None:
        """
        Roll back the transaction, returning the connection to the pool.
        """
        a = self._original(True)
        try:
            await a.rollback()
        finally:
            await self._pool._checkin(self, a)

    async def _closeCursors(self) -> None:
        for cursor in self._cursors:
            await cursor.close()

    async def commit(self) -> None:
        """
        Commit the transaction, returning the connection to the pool.
        """
        await self._closeCursors()
        a = self._original(True)
        try:
            await a.commit()
        finally:
            await self._pool._checkin(self, a)

    async def close(self) -> None:
        """
        Close the underlying connection, removing it from the pool.
        """
        await self._closeCursors()
        await self._original(True).close()


@dataclass(eq=False)
class ThreadedConnectionPool:
    """
    Database engine and connection pool.
    """

    _connectCallable: Callable[[], DBAPIConnection]
    paramstyle: ParamStyle
    _idleMax: int
    _createWorker: Callable[[], IExclusiveWorker]
    _deliver: Callable[[Callable[[], None]], None]
    _idlers: List[ThreadedConnectionAdapter] = field(default_factory=list)
    _active: List[PooledThreadedConnectionAdapter] = field(default_factory=list)

    async def connect(self) -> PooledThreadedConnectionAdapter:
        """
        Checkout a new connection from the pool, connecting to the database and
        opening a thread first if necessary.
        """
        if self._idlers:
            conn = self._idlers.pop()
        else:
            e = ExclusiveWorkQueue(self._createWorker(), self._deliver)
            conn = ThreadedConnectionAdapter(
                await e.perform(self._connectCallable),
                e,
                self.paramstyle,
            )
        txn = PooledThreadedConnectionAdapter(conn, self, [])
        self._active.append(txn)
        return txn

    async def _checkin(
        self,
        txn: PooledThreadedConnectionAdapter,
        connection: ThreadedConnectionAdapter,
    ) -> None:
        """
        Check a connection back in to the pool, closing and discarding it.
        """
        self._active.remove(txn)
        if len(self._idlers) < self._idleMax:
            self._idlers.append(connection)
        else:
            await connection.close()

    async def quit(self) -> None:
        """
        Close all outstanding connections and shut down the underlying
        threadpool.
        """
        self._idleMax = 0
        while self._active:
            await self._active[0].rollback()

        while self._idlers:
            await self._idlers.pop().close()


def adaptSynchronousDriver(
    connectCallable: Callable[[], DBAPIConnection],
    paramstyle: ParamStyle,
    *,
    createWorker: Optional[Callable[[], IExclusiveWorker]] = None,
    callFromThread: Optional[Callable[[F], None]] = None,
    maxIdleConnections: int = 5,
) -> AsyncConnectable:
    """
    Adapt a synchronous DB-API driver to be an L{AsyncConnectable}.
    """
    if callFromThread is None:
        reactor: Any
        from twisted.internet import reactor

        callFromThread = reactor.callFromThread

    if createWorker is None:
        createWorker = _newThread

    return ThreadedConnectionPool(
        connectCallable,
        paramstyle,
        maxIdleConnections,
        createWorker,
        callFromThread,
    )


if TYPE_CHECKING:
    _1: Type[AsyncCursor] = ThreadedCursorAdapter
    _2: Type[AsyncConnection] = ThreadedConnectionAdapter
    _4: Type[AsyncConnection] = PooledThreadedConnectionAdapter
    _3: Type[AsyncConnectable] = ThreadedConnectionPool
