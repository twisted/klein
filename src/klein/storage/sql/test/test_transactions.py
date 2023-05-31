"""
Tests for L{klein.storage.sql._transactions}
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, Optional

from treq import content
from treq.testing import StubTreq

from twisted.internet.defer import Deferred
from twisted.trial.unittest import SynchronousTestCase

from klein import Klein, Requirer
from klein.storage.sql._transactions import Transaction

from ...dbaccess.dbapi_async import AsyncConnectable, AsyncConnection
from ...dbaccess.testing import MemoryPool


@dataclass
class TestObject:
    """
    Object to test request commit hooks.
    """

    testCase: SynchronousTestCase
    connectable: AsyncConnectable
    t1: Optional[AsyncConnection] = None
    t2: Optional[AsyncConnection] = None
    incomplete: Deferred[None] = field(default_factory=Deferred)

    router: ClassVar[Klein] = Klein()
    requirer: ClassVar[Requirer] = Requirer()

    def _getDB(self) -> AsyncConnectable:
        return self.connectable

    @requirer.require(
        router.route("/succeed"),
        t1=Transaction(_getDB),
        t2=Transaction(_getDB),
    )
    async def succeed(self, t1: AsyncConnection, t2: AsyncConnection) -> str:
        """
        Get a transaction that commits when the request has completed.
        """
        self.t1 = t1
        await self.incomplete
        self.t2 = t2
        return "Hello, world!"


class WriteHeadersHookTests(SynchronousTestCase):
    """
    Tests for L{klein.storage.sql._transactions}.
    """

    def test_sameTransactions(self) -> None:
        """
        If a transaction is required multiple times, it results in the same
        object.
        """
        mpool = MemoryPool.new()
        to = TestObject(self, mpool.connectable)
        stub = StubTreq(to.router.resource())
        inProgress = stub.get("https://localhost/succeed")
        self.assertNoResult(inProgress)
        mpool.flush()
        to.incomplete.callback(None)
        self.assertNoResult(inProgress)
        mpool.flush()
        stub.flush()
        response = self.successResultOf(inProgress)
        self.assertIsNot(to.t1, None)
        self.assertIs(to.t1, to.t2)
        self.assertEqual(
            self.successResultOf(content(response)), b"Hello, world!"
        )

    def test_everythingCommitted(self) -> None:
        """
        Completing the request commits the transaction.
        """
        mpool = MemoryPool.new()
        mpool.flush()
