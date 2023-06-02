from typing import List

from twisted.trial.unittest import SynchronousTestCase, TestCase

from ..._util import eagerDeferredCoroutine
from ..passwords import (
    InvalidPasswordRecord,
    KleinV1PasswordEngine,
    PasswordEngine,
    engineForTesting,
)


class PasswordStorageTests(TestCase):
    def setUp(self) -> None:
        self.newHashes: List[str] = []
        self.engine: PasswordEngine = KleinV1PasswordEngine(2**14, 2**15)

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

    @eagerDeferredCoroutine
    async def test_serializationErrorHandling(self) -> None:
        """
        Un-parseable passwords will result in a L{BadStoredPassword} exception.
        """
        engine = KleinV1PasswordEngine(2**5, 2**6)
        with self.assertRaises(InvalidPasswordRecord):
            await engine.checkAndReset(
                "gibberish", "my-password", self.storeSomething
            )


class TestTesting(SynchronousTestCase):
    """
    Tests for L{engineForTesting}
    """

    def test_testingEngine(self) -> None:
        """
        A cached password engine can verify passwords.
        """
        changes: List[str] = []
        engine1 = engineForTesting(self)
        engine2 = engineForTesting(self)
        # The same test should get back the same engine.
        self.assertIs(engine1, engine2)
        # should complete synchronously
        kt1 = self.successResultOf(engine1.computeKeyText("hello world"))

        async def storeSomething(something: str) -> None:
            changes.append(something)

        self.assertEqual(
            True,
            self.successResultOf(
                engine1.checkAndReset(
                    kt1,
                    "hello world",
                    storeSomething,
                )
            ),
        )
        self.assertEqual(
            False,
            self.successResultOf(
                engine1.checkAndReset(
                    kt1,
                    "hello wordl",
                    storeSomething,
                )
            ),
        )
