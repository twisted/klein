"""
Tests for running synchronous DB-API drivers within threads.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from itertools import count
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
)

from zope.interface import implementer

from twisted._threads import AlreadyQuit
from twisted._threads._ithreads import IExclusiveWorker
from twisted.internet.defer import Deferred
from twisted.trial.unittest import TestCase

from ...._util import eagerDeferredCoroutine
from .._dbapi_async_twisted import ExclusiveWorkQueue, ThreadedConnectionPool
from .._testing import sqlite3Connector
from ..dbapi_async import (
    AsyncConnectable,
    InvalidConnection,
    adaptSynchronousDriver,
    transaction,
)
from ..dbapi_sync import DBAPIColumnDescription, DBAPIConnection, DBAPICursor


pretendThreadID = 0


@contextmanager
def pretendToBeInThread(newThreadID: int) -> Iterator[None]:
    """
    Pretend to be in the given thread while executing.
    """
    global pretendThreadID
    pretendThreadID = newThreadID
    try:
        yield
    finally:
        pretendThreadID = newThreadID


@dataclass
class FakeDBAPICursor:
    """
    Fake PEP 249 cursor.
    """

    connection: FakeDBAPIConnection
    arraysize: int
    cursorID: int = field(default_factory=count().__next__)

    @property
    def operationsByThread(self) -> List[Tuple[str, int, int]]:
        """
        Delegate to connection.
        """
        return self.connection.operationsByThread

    @property
    def connectionID(self) -> int:
        """
        Delegate to connection.
        """
        return self.connection.connectionID

    @property
    def description(self) -> Optional[Sequence[DBAPIColumnDescription]]:
        # note sqlite actually pads out the response with Nones like this
        self.operationsByThread.append(
            ("description", self.connectionID, pretendThreadID)
        )
        return [("stub", None, None, None, None, None, None)]

    @property
    def rowcount(self) -> int:
        self.operationsByThread.append(
            ("rowcount", self.connectionID, pretendThreadID)
        )
        return 0

    def close(self) -> object:
        self.operationsByThread.append(
            ("close", self.connectionID, pretendThreadID)
        )
        return None

    def execute(
        self,
        operation: str,
        parameters: Union[Sequence[Any], Mapping[str, Any]] = (),
    ) -> object:
        self.operationsByThread.append(
            ("execute", self.connectionID, pretendThreadID)
        )
        return None

    def executemany(
        self, __operation: str, __seq_of_parameters: Sequence[Sequence[Any]]
    ) -> object:
        self.operationsByThread.append(
            ("executemany", self.connectionID, pretendThreadID)
        )
        return None

    def fetchone(self) -> Optional[Sequence[Any]]:
        self.operationsByThread.append(
            ("fetchone", self.connectionID, pretendThreadID)
        )
        return None

    def fetchmany(self, __size: int = 0) -> Sequence[Sequence[Any]]:
        self.operationsByThread.append(
            ("fetchmany", self.connectionID, pretendThreadID)
        )
        return []

    def fetchall(self) -> Sequence[Sequence[Any]]:
        self.operationsByThread.append(
            ("fetchall", self.connectionID, pretendThreadID)
        )
        return []


@dataclass
class FakeDBAPIConnection:
    """
    Fake PEP 249 connection.
    """

    cursors: list[FakeDBAPICursor]
    # (operation, connectionID, threadID)
    operationsByThread: list[tuple[str, int, int]]
    connectionID: int = field(default_factory=count().__next__)

    def close(self) -> None:
        self.operationsByThread.append(
            ("connection.close", self.connectionID, pretendThreadID)
        )
        return None

    def commit(self) -> None:
        self.operationsByThread.append(
            ("commit", self.connectionID, pretendThreadID)
        )
        return None

    def rollback(self) -> Any:
        self.operationsByThread.append(
            ("rollback", self.connectionID, pretendThreadID)
        )

    def cursor(self) -> DBAPICursor:
        self.operationsByThread.append(
            ("cursor", self.connectionID, pretendThreadID)
        )
        cursor = FakeDBAPICursor(self, 3)
        self.cursors.append(cursor)
        return cursor


if TYPE_CHECKING:
    _1: Type[DBAPICursor] = FakeDBAPICursor
    _2: Type[DBAPIConnection] = FakeDBAPIConnection


def realThreadedAdapter(testCase: TestCase) -> AsyncConnectable:
    """
    Create an AsyncConnectable using real threads and scheduling its
    non-threaded callbacks on the Twisted reactor, suitable for using in a
    real-Deferred-returning integration test.
    """
    memdb = sqlite3Connector()
    scon = memdb()

    scur = scon.cursor()
    scur.execute(
        """
    create table sample (testcol int primary key, testcol2 str)
    """
    )
    scur.execute(
        """
    insert into sample values (1, 'hello'), (2, 'goodbye')
    """
    )
    scon.commit()

    pool = adaptSynchronousDriver(memdb, sqlite3.paramstyle)
    testCase.addCleanup(lambda: Deferred.fromCoroutine(pool.quit()))
    return pool


Thunk = Callable[[], None]


def wrap(t: Thunk, threadID: int) -> Thunk:
    """
    Wrap the given thunk in a fake thread ID
    """

    def wrapped() -> None:
        with pretendToBeInThread(threadID):
            t()

    return wrapped


@implementer(IExclusiveWorker)
@dataclass
class FakeExclusiveWorker:
    queue: List[Thunk]
    threadID: int = field(default_factory=count().__next__)
    quitted: bool = False

    def do(self, work: Callable[[], None]) -> None:
        assert (
            not self.quitted
        ), "we should never schedule work on a quitted worker"
        self.queue.append(wrap(work, self.threadID))

    def quit(self) -> None:
        """
        Exit & clean up.
        """
        self.quitted = True


class SampleError(Exception):
    """
    An error occurred.
    """


class ResourceManagementTests(TestCase):
    """
    Tests to make sure that various thread resources are managed correctly.
    """

    def setUp(self) -> None:
        """
        set up a thread pool that pretends to start threads
        """
        # this queue of work is both "in threads" and "not in threads" work;
        # all "in threads" work is wrapped up in a thing that sets the global
        # L{pretendThreadID}; all "main thread" work has it set to 0.
        self.queue: List[Thunk] = []
        self.cursors: List[FakeDBAPICursor] = []
        self.dbapiops: List[Tuple[str, int, int]] = []
        self.threads: List[FakeExclusiveWorker] = []

        def newWorker() -> IExclusiveWorker:
            w = FakeExclusiveWorker(self.queue)
            self.threads.append(w)
            return w

        def makeConnection() -> DBAPIConnection:
            conn = FakeDBAPIConnection(self.cursors, self.dbapiops)
            self.dbapiops.append(
                ("connect", conn.connectionID, pretendThreadID)
            )
            return conn

        self.poolInternals = ThreadedConnectionPool(
            makeConnection,
            "qmark",
            3,
            newWorker,
            self.queue.append,
        )
        self.pool: AsyncConnectable = self.poolInternals

    def flush(self) -> None:
        """
        Perform all outstanding "threaded" work.
        """
        while self.queue:
            self.queue.pop(0)()

    def test_allOperations(self) -> None:
        """
        All the DB-API operations are wrapped.
        """

        async def dostuff() -> None:
            con = await self.pool.connect()
            cur = await con.cursor()
            self.assertEqual(
                await cur.description(),
                [("stub", None, None, None, None, None, None)],
            )
            self.assertEqual(await cur.rowcount(), 0)
            await cur.execute("test expr", ["some", "params"]), []
            await cur.executemany(
                "lots of operations", [["parameter", "seq"], ["etc", "etc"]]
            )
            self.assertIs(await cur.fetchone(), None)
            self.assertEqual(await cur.fetchmany(7), [])
            self.assertEqual(await cur.fetchall(), [])
            await cur.close()
            await con.commit()
            # already committed, so we need a new connection to test rollback
            con2 = await self.pool.connect()
            await con2.rollback()

        d1 = Deferred.fromCoroutine(dostuff())
        self.flush()
        self.successResultOf(d1)
        self.assertOperations(
            [
                "connect",
                "cursor",
                "description",
                "rowcount",
                "execute",
                "executemany",
                "fetchone",
                "fetchmany",
                "fetchall",
                "close",
                "close",
                "commit",
                "rollback",
            ],
        )

    def test_connectionClose(self) -> None:
        """
        As opposed to committing or rolling back, closing a connection will
        remove it from the pool entirely.
        """

        async def dostuff() -> None:
            con = await self.pool.connect()
            await con.close()
            with self.assertRaises(InvalidConnection):
                await con.cursor()
            with self.assertRaises(InvalidConnection):
                await con.close()

        d1 = Deferred.fromCoroutine(dostuff())
        self.flush()
        self.successResultOf(d1)
        self.assertOperations(["connect", "connection.close"])
        self.assertEqual(self.poolInternals._idlers, [])
        # The associated thread is also quit.
        self.assertEqual([thread.quitted for thread in self.threads], [True])

    def assertOperations(self, expectedOperations: Sequence[str]) -> None:
        """
        Assert that DB-API would have performed the named operations.
        """
        self.assertEqual(
            expectedOperations, [first for first, _, _ in self.dbapiops]
        )

    def test_inCorrectThread(self) -> None:
        """
        Each connection's operations are executed on a dedicated thread.
        """

        async def dostuff() -> None:
            con = await self.pool.connect()
            cur = await con.cursor()
            await cur.execute("select * from what")
            await con.commit()

        d1 = Deferred.fromCoroutine(dostuff())
        d2 = Deferred.fromCoroutine(dostuff())
        self.assertNoResult(d1)
        self.assertNoResult(d2)
        self.flush()

        self.successResultOf(d1)
        self.successResultOf(d2)

        async def cleanup() -> None:
            await self.pool.quit()

        cleanedup = Deferred.fromCoroutine(cleanup())
        self.flush()

        self.successResultOf(cleanedup)
        self.assertEqual((self.poolInternals._idlers), [])

        threadToConnection: Dict[int, int] = {}
        connectionToThread: Dict[int, int] = {}
        confirmed = 0

        for _, connectionID, threadID in self.dbapiops:
            if threadID in threadToConnection:
                self.assertEqual(threadToConnection[threadID], connectionID)
                self.assertEqual(connectionToThread[connectionID], threadID)
                confirmed += 1
            else:
                threadToConnection[threadID] = connectionID
                connectionToThread[connectionID] = threadID
        # ops = ['connect', 'cursor', 'execute', 'close', 'commit', 'close']
        # expected = (len(ops) * 2) - 2
        expected = 10
        self.assertEqual(confirmed, expected)
        self.assertEqual(len(threadToConnection), 2)

    def test_basicPooling(self) -> None:
        """
        When a pooled connection is committed or rolled back, we will
        invalidate it and won't allocate additional underlying connections.
        """

        async def t1() -> None:
            con = await self.pool.connect()
            await con.commit()
            with self.assertRaises(InvalidConnection):
                await con.cursor()
            con = await self.pool.connect()
            await con.rollback()
            with self.assertRaises(InvalidConnection):
                await con.cursor()

        d = Deferred.fromCoroutine(t1())
        self.flush()
        self.successResultOf(d)
        self.assertEqual(
            len({connectionID for _, connectionID, _ in self.dbapiops}), 1
        )

    def test_tooManyConnections(self) -> None:
        """
        When we exceed the idle-max of the pool, we close connections
        immediately as they are returned.
        """

        async def t1() -> None:
            c1 = await self.pool.connect()
            c2 = await self.pool.connect()
            c3 = await self.pool.connect()
            c4 = await self.pool.connect()
            await c1.commit()
            await c2.commit()
            await c3.commit()
            await c4.commit()

        d = Deferred.fromCoroutine(t1())
        self.flush()
        self.successResultOf(d)
        self.assertEqual(len(self.poolInternals._idlers), 3)
        self.assertOperations(
            [
                *["connect"] * 4,
                *["commit"] * 4,
                "connection.close",
            ]
        )

    def test_transactionContextManager(self) -> None:
        """
        C{with transaction(pool)} results in an async context manager which
        will commit when exited normally and rollback when exited with an
        exception.
        """

        async def t1() -> None:
            # committed
            async with transaction(self.pool) as t:
                await (await t.cursor()).execute("hello world")

            # rolled back
            with self.assertRaises(SampleError):
                async with transaction(self.pool) as t2:
                    await (await t2.cursor()).execute("a")
                    raise SampleError()

        started = Deferred.fromCoroutine(t1())
        self.flush()
        self.successResultOf(started)
        self.assertOperations(
            [
                "connect",
                "cursor",
                "execute",
                "close",
                "commit",
                "cursor",
                "execute",
                "rollback",
            ]
        )

    def test_poolQuit(self) -> None:
        """
        When the pool is shut down, all idlers are closed, and all active
        connections invalidated.
        """

        async def t1() -> None:
            c1 = await self.pool.connect()
            c2 = await self.pool.connect()
            await self.pool.quit()
            with self.assertRaises(InvalidConnection):
                await c1.cursor()
            with self.assertRaises(InvalidConnection):
                await c2.cursor()

        d = Deferred.fromCoroutine(t1())
        self.flush()
        self.successResultOf(d)
        self.assertOperations(
            [
                "connect",
                "connect",
                "rollback",
                "connection.close",
                "rollback",
                "connection.close",
            ]
        )
        self.assertEqual(self.poolInternals._idlers, [])
        self.assertEqual(len(self.threads), 2)
        self.assertEqual(self.threads[0].quitted, True)
        self.assertEqual(self.threads[1].quitted, True)


class InternalSafetyTests(TestCase):
    """
    Tests for internal safety mechanisms; states which I{should} be unreachable
    via the public API but should nonetheless be reported.
    """

    def test_queueQuit(self) -> None:
        """
        L{ExclusiveWorkQueue} should raise L{AlreadyQuit} when interacted with
        after C{quit}.
        """
        stuff: List[Callable[[], None]] = []
        ewc = ExclusiveWorkQueue(FakeExclusiveWorker(stuff), stuff.append)
        ewc.quit()
        with self.assertRaises(AlreadyQuit):
            ewc.quit()
        with self.assertRaises(AlreadyQuit):
            ewc.perform(int)
        self.assertEqual(stuff, [])


class SyncAdapterTests(TestCase):
    """
    Integration tests for L{adaptSynchronousDriver}.
    """

    @eagerDeferredCoroutine
    async def test_execAndFetch(self) -> None:
        """
        Integration test: can we use an actual DB-API module, with real threads?
        """
        pool = realThreadedAdapter(self)
        con = await pool.connect()
        cur = await con.cursor()

        query = """
        select * from sample order by testcol asc
        """
        await cur.execute(query)
        self.assertEqual(await cur.fetchall(), [(1, "hello"), (2, "goodbye")])
        await cur.execute(
            """
            insert into sample values (3, 'more'), (4, 'even more')
            """
        )
        await cur.execute(query)
        self.assertEqual(
            await cur.fetchmany(3), [(1, "hello"), (2, "goodbye"), (3, "more")]
        )
        self.assertEqual(await cur.fetchmany(3), [(4, "even more")])

    @eagerDeferredCoroutine
    async def test_errors(self) -> None:
        """
        Integration test: do errors propagate?
        """
        pool = realThreadedAdapter(self)
        con = await pool.connect()
        cur = await con.cursor()
        later = cur.execute("select * from nonexistent")
        with self.assertRaises(sqlite3.OperationalError) as oe:
            await later
        self.assertIn("nonexistent", str(oe.exception))

    @eagerDeferredCoroutine
    async def test_invalidateAfterCommit(self) -> None:
        """
        Connections will be invalidated after they've been committed.
        """
        pool = realThreadedAdapter(self)
        con = await pool.connect()
        await con.commit()
        with self.assertRaises(InvalidConnection):
            await con.cursor()
