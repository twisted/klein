from collections.abc import AsyncIterable
from typing import TypeVar
from unittest import TestCase

from dbxs.async_dbapi import transaction
from dbxs.testing import MemoryPool, immediateTest

from .._sql_dal import SessionDB
from .._sql_glue import applyBasicSchema

T = TypeVar("T")


async def asyncList(i: AsyncIterable[T]) -> list[T]:
    result = []
    async for value in i:
        result.append(value)
    return result


class CreateAndDeleteSessions(TestCase):
    @immediateTest()
    async def test_createAndDelete(self, pool: MemoryPool) -> None:
        """
        L{SessionDB} has methods that can create and delete accounts and
        sessions, and bind and unbind them.
        """
        # It might be nice to split this out into some different tests, but
        # everything here is interdependent state and so it all needs to be run
        # in a particular order or related to each other anyway, so we'll just
        # do one big test for now.
        await applyBasicSchema(pool.connectable)
        async with transaction(pool.connectable) as c:
            cur = await c.cursor()
            await cur.execute("PRAGMA foreign_keys = ON")
            db = SessionDB(c)
            accountID = "asdf"
            username = "username1"
            await db.createAccount(
                accountID, username, "user@example.com", "invalid password blob"
            )
            await db.createAccount(
                "fdsa",
                "username2",
                "other@example.com",
                "other invalid password blob",
            )
            account = await db.accountByUsername("nobody")
            self.assertIs(account, None)
            account = await db.accountByUsername(username)
            assert account is not None
            self.assertEqual(account.username, username)
            now = 4321.0
            await db.insertSession(
                "secure-session", True, now, "opaque-mechanism"
            )
            await db.insertSession(
                "insecure-session", False, now, "opaque-mechanism-2"
            )
            await db.insertSession(
                "unused-session", True, now, "opaque-mechanism"
            )
            await db.insertSession(
                "other-session", True, now, "opaque-mechanism"
            )
            self.assertEqual(
                await asyncList(db.boundAccounts("secure-session")), []
            )
            await db.bindAccountToSession(accountID, "secure-session")
            await db.bindAccountToSession(accountID, "insecure-session")
            self.assertEqual(
                await asyncList(db.boundAccounts("secure-session")), [account]
            )
            self.assertEqual(
                await asyncList(db.boundAccounts("insecure-session")), [account]
            )
            await db.deleteSession("secure-session", False)
            self.assertEqual(
                await asyncList(db.boundAccounts("secure-session")), [account]
            )
            await db.deleteSession("secure-session", True)
            self.assertEqual(
                await asyncList(db.boundAccounts("secure-session")), []
            )
            await db.deleteSession("insecure-session", False)
            self.assertEqual(
                await asyncList(db.boundAccounts("insecure-session")), []
            )
