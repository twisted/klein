from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from twisted.trial.unittest import SynchronousTestCase as TestCase

from ...._typing_compat import Protocol
from .. import (
    ExtraneousMethods,
    NotEnoughResults,
    ParamMismatch,
    TooManyResults,
    accessor,
    maybe,
    one,
    query,
    statement,
)
from ..dbapi_async import AsyncConnection, transaction
from ..testing import MemoryPool, immediateTest


# Trying to stick to the public API for what we're testing; no underscores here.


@dataclass
class Foo:
    db: FooAccessPattern
    bar: int
    baz: int


class FooAccessPattern(Protocol):
    @query(sql="select bar, baz from foo where bar = {bar}", load=one(Foo))
    async def getFoo(self, bar: int) -> Foo:
        ...

    @query(sql="select bar, baz from foo where bar = {bar}", load=maybe(Foo))
    async def maybeFoo(self, bar: int) -> Optional[Foo]:
        ...

    @query(sql="select bar, baz from foo where baz = {baz}", load=one(Foo))
    async def oneFooByBaz(self, baz: int) -> Foo:
        ...

    @query(sql="select bar, baz from foo where baz = {baz}", load=maybe(Foo))
    async def maybeFooByBaz(self, baz: int) -> Optional[Foo]:
        ...

    @statement(sql="insert into foo (baz) values ({baz})")
    async def newFoo(self, baz: int) -> None:
        """
        Create a new C{Foo}
        """

    @statement(sql="select * from foo")
    async def oopsQueryNotStatement(self) -> None:
        """
        Oops, it's a query, not a statement, it returns values.
        """

    @query(
        sql="insert into foo (baz) values ({baz}) returning bar, baz",
        load=one(Foo),
    )
    async def newReturnFoo(self, baz: int) -> Foo:
        """
        Create a new C{Foo} and return it.
        """


accessFoo = accessor(FooAccessPattern)


async def schemaAndData(c: AsyncConnection) -> None:
    """
    Create the schema for 'foo' and insert some sample data.
    """
    cur = await c.cursor()
    for stmt in """
        create table foo (bar integer primary key autoincrement, baz int);
        insert into foo values (1, 3);
        insert into foo values (2, 4);
        """.split(
        ";"
    ):
        await cur.execute(stmt)


class AccessTestCase(TestCase):
    """
    Tests for L{accessor} and its associated functions
    """

    @immediateTest()
    async def test_happyPath(self, pool: MemoryPool) -> None:
        """
        Declaring a protocol with a query and executing it
        """
        async with transaction(pool.connectable) as c:
            await schemaAndData(c)
            db = accessFoo(c)
            result = await db.getFoo(1)
            result2 = await db.maybeFoo(1)
        self.assertEqual(result, Foo(db, 1, 3))
        self.assertEqual(result, result2)

    def test_argumentExhaustiveness(self) -> None:
        """
        If a query does not use all of its arguments, or the function does not
        specify all the arguments that a function uses, it will raise an
        exception during definition.
        """
        with self.assertRaises(ParamMismatch) as pm:

            class MissingBar(Protocol):
                @statement(sql="fake sql {bar}")
                async def someUnused(self) -> None:
                    ...

        self.assertIn("bar", str(pm.exception))
        self.assertIn("someUnused", str(pm.exception))
        with self.assertRaises(ParamMismatch):

            class DoesntUseBar(Protocol):
                @statement(sql="fake sql")
                async def someMissing(self, bar: str) -> None:
                    ...

    @immediateTest()
    async def test_tooManyResults(self, pool: MemoryPool) -> None:
        """
        If there are too many results for a L{one} query, then a
        L{TooManyResults} exception is raised.
        """
        async with transaction(pool.connectable) as c:
            await schemaAndData(c)
            cur = await c.cursor()
            await cur.execute("insert into foo (baz) values (3)")
            await cur.execute("insert into foo (baz) values (3)")
            db = accessFoo(c)
            with self.assertRaises(TooManyResults):
                await db.oneFooByBaz(3)
            with self.assertRaises(TooManyResults):
                await db.maybeFooByBaz(3)

    def test_brokenProtocol(self) -> None:
        """
        Using L{accessor} on a protocol with unrelated methods raises a .
        """

        class NonAccessPatternProtocol(Protocol):
            def randomNonQueryMethod(self) -> None:
                ...

        with self.assertRaises(ExtraneousMethods) as em:
            accessor(NonAccessPatternProtocol)
        self.assertIn("randomNonQueryMethod", str(em.exception))

    @immediateTest()
    async def test_notEnoughResults(self, pool: MemoryPool) -> None:
        """
        If there are too many results for a L{one} query, then a
        L{NotEnoughResults} exception is raised.
        """
        async with transaction(pool.connectable) as c:
            cur = await c.cursor()
            await schemaAndData(c)
            await cur.execute("delete from foo")
            db = accessFoo(c)
            with self.assertRaises(NotEnoughResults):
                await db.getFoo(1)
            self.assertIs(await db.maybeFoo(1), None)

    @immediateTest()
    async def test_insertStatementWithReturn(self, pool: MemoryPool) -> None:
        """
        DML statements can use RETURNING to return values.
        """
        async with transaction(pool.connectable) as c:
            await schemaAndData(c)
            db = accessFoo(c)
            self.assertEqual(await db.newReturnFoo(100), Foo(db, 3, 100))

    @immediateTest()
    async def test_statementHasNoResult(self, pool: MemoryPool) -> None:
        """
        The L{statement} decorator gives a result.
        """
        async with transaction(pool.connectable) as c:
            await schemaAndData(c)
            db = accessFoo(c)
            nothing = await db.newFoo(7)  # type:ignore[func-returns-value]
            self.assertIs(nothing, None)

    @immediateTest()
    async def test_statementWithResultIsError(self, pool: MemoryPool) -> None:
        """
        The L{statement} decorator gives a result.
        """
        async with transaction(pool.connectable) as c:
            await schemaAndData(c)
            db = accessFoo(c)
            with self.assertRaises(TooManyResults) as tmr:
                await db.oopsQueryNotStatement()
            self.assertIn("should not return", str(tmr.exception))
