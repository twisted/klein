# -*- test-case-name: klein.storage.dbxs.test -*-
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, List, TypeVar
from uuid import uuid4

from twisted._threads._ithreads import IExclusiveWorker
from twisted._threads._memory import createMemoryWorker
from twisted.internet.defer import Deferred
from twisted.trial.unittest import SynchronousTestCase

from ._dbapi_types import DBAPIConnection
from .dbapi_async import AsyncConnectable, adaptSynchronousDriver


def sqlite3Connector() -> Callable[[], DBAPIConnection]:
    """
    Create an in-memory shared-cache SQLite3 database and return a 0-argument
    callable that will connect to that database.
    """
    uri = f"file:{str(uuid4())}?mode=memory&cache=shared"

    held = None

    def connect() -> DBAPIConnection:
        # This callable has to hang on to a connection to the underlying SQLite
        # data structures, otherwise its schema and shared cache disappear as
        # soon as it's garbage collected.  This 'nonlocal' stateemnt adds it to
        # the closure, which keeps the reference after it's created.
        nonlocal held
        return sqlite3.connect(uri, uri=True)

    held = connect()
    return connect


@dataclass
class MemoryPool:
    """
    An in-memory connection pool to an in-memory SQLite database which can be
    controlled a single operation at a time.  Each operation that would
    normally be asynchronoulsy dispatched to a thread can be invoked with the
    L{MemoryPool.pump} and L{MemoryPool.flush} methods.

    @ivar connectable: The L{AsyncConnectable} to be passed to the system under
        test.
    """

    connectable: AsyncConnectable
    _performers: List[Callable[[], bool]]

    def additionalPump(self, f: Callable[[], bool]) -> None:
        """
        Add an additional callable to be called by L{MemoryPool.pump} and
        L{MemoryPool.flush}.  This can be used to interleave other sources of
        in-memory event completion to allow test coroutines to complete, such
        as needing to call L{StubTreq.flush}.
        """
        self._performers.append(f)

    def pump(self) -> bool:
        """
        Perform one step of pending work.

        @return: True if any work was performed and False if no work was left.
        """
        for performer in self._performers:
            if performer():
                return True
        return False

    def flush(self) -> int:
        """
        Perform all outstanding steps of work.

        @return: a count of the number of steps of work performed.
        """
        steps = 0
        while self.pump():
            steps += 1
        return steps

    @classmethod
    def new(cls) -> MemoryPool:
        """
        Create a synchronous memory connection pool.
        """
        performers = []

        def createWorker() -> IExclusiveWorker:
            worker: IExclusiveWorker
            # note: createMemoryWorker actually returns IWorker, better type
            # annotations may require additional shenanigans
            worker, perform = createMemoryWorker()
            performers.append(perform)
            return worker

        return MemoryPool(
            adaptSynchronousDriver(
                sqlite3Connector(),
                sqlite3.paramstyle,
                createWorker=createWorker,
                callFromThread=lambda f: f(),
                maxIdleConnections=10,
            ),
            performers,
        )


AnyTestCase = TypeVar("AnyTestCase", bound=SynchronousTestCase)
syncAsyncTest = Callable[
    [AnyTestCase, MemoryPool],
    Coroutine[Any, Any, None],
]
regularTest = Callable[[AnyTestCase], None]


def immediateTest() -> (
    Callable[[syncAsyncTest[AnyTestCase]], regularTest[AnyTestCase]]
):
    """
    Decorate an C{async def} test that expects a coroutine.
    """

    def decorator(decorated: syncAsyncTest[AnyTestCase]) -> regularTest:
        def regular(self: AnyTestCase) -> None:
            pool = MemoryPool.new()
            d = Deferred.fromCoroutine(decorated(self, pool))
            self.assertNoResult(d)
            while pool.flush():
                pass
            self.successResultOf(d)

        return regular

    return decorator
