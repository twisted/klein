from typing import List

from twisted.trial.unittest import TestCase

from ..._util import eagerDeferredCoroutine
from .._passwords import KleinV1PasswordEngine


class PasswordStorageTests(TestCase):
    def setUp(self) -> None:
        self.newHashes: List[str] = []
        self.engine = KleinV1PasswordEngine(2**14, 2**15)

    @eagerDeferredCoroutine
    async def storeSomething(self, something: str) -> None:
        self.newHashes.append(something)

    @eagerDeferredCoroutine
    async def test_checkAndResetDefault(self) -> None:
        """
        Tests for L{checkAndReset} and L{computeHash} functions.  These are a
        little slow because they're verifying the normal / good default of the
        production-grade CryptContext hash.
        """
        kt1 = await self.engine.computeKeyText("hello world")
        bad = await self.engine.checkAndReset(
            kt1, "hello wordl", self.storeSomething
        )
        self.assertFalse(bad, "passwords don't match")
        good = await self.engine.checkAndReset(
            kt1, "hello world", self.storeSomething
        )
        self.assertTrue(good, "passwords do match")
        self.assertEqual(self.newHashes, [])

    @eagerDeferredCoroutine
    async def test_resetOnNewRounds(self) -> None:
        """
        When the supplied CryptContext requires more rounds, the store function
        will be called.
        """
        oldEngine = KleinV1PasswordEngine(2**10, 2**12)
        kt1 = await oldEngine.computeKeyText("hello world")
        check1 = await self.engine.checkAndReset(
            kt1, "hello world", self.storeSomething
        )
        self.assertTrue(check1)
        self.assertEqual(len(self.newHashes), 1)
        newHash = self.newHashes.pop()
        check2 = await self.engine.checkAndReset(
            newHash, "hello world", self.storeSomething
        )
        self.assertTrue(check2)
        self.assertEqual(self.newHashes, [])
