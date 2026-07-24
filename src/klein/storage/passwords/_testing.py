# -*- test-case-name: klein.storage.passwords.test.test_passwords -*-

from dataclasses import dataclass, field
from hashlib import sha256
from os import urandom
from typing import Awaitable, Callable, Optional
from unicodedata import normalize
from unittest import TestCase

from ._interfaces import PasswordEngine


@dataclass
class InsecurePasswordEngineOnlyForTesting:
    """
    Very fast in-memory password engine that is suitable only for testing.
    """

    tempSalt: bytes = field(default_factory=lambda: urandom(16))
    hashVersion: int = 1
    upgradedHashes: int = 0

    async def computeKeyText(self, passwordText: str) -> str:
        # hashing here only in case someone *does* put this into production;
        # the salt will be lost, and this will be garbage, so all auth will
        # fail.
        return (
            f"{self.hashVersion}-"
            + sha256(
                normalize("NFD", passwordText).encode("utf-8") + self.tempSalt
            ).hexdigest()
        )

    async def checkAndReset(
        self,
        storedPasswordHash: str,
        providedPasswordText: str,
        storeNewHash: Callable[[str], Awaitable[None]],
    ) -> bool:
        storedVersion, storedActualHash = storedPasswordHash.split("-")
        computedHash = await self.computeKeyText(providedPasswordText)
        newVersion, receivedActualHash = computedHash.split("-")
        valid = storedActualHash == receivedActualHash
        if valid and int(newVersion) > int(storedVersion):
            await storeNewHash(computedHash)
            self.upgradedHashes += 1
        return valid


cacheAttribute = "__insecurePasswordEngine__"


def engineForTesting(
    testCase: TestCase, *, upgradeHashes: bool = False
) -> PasswordEngine:
    """
    Return an insecure password engine that is very fast, suitable for using in
    unit tests.

    @param testCase: The test case for which this engine is to be used.  The
        engine will be cached on the test case, so that multiple calls will
        return the same object.

    @param storeNewHashes: Should the engine's C{checkAndReset} method call its
        C{storePasswordHash} argument?  Note that this mutates the existing
        engine if one has already been cached.
    """
    result: Optional[InsecurePasswordEngineOnlyForTesting] = getattr(
        testCase, cacheAttribute, None
    )
    if result is None:
        result = InsecurePasswordEngineOnlyForTesting()
        setattr(testCase, cacheAttribute, result)
    result.hashVersion += upgradeHashes
    return result


def hashUpgradeCount(testCase: TestCase) -> int:
    """
    How many times has the L{engineForTesting} for the given test upgraded the
    hash of a stored password?
    """
    engine = engineForTesting(testCase)
    assert isinstance(engine, InsecurePasswordEngineOnlyForTesting)
    return engine.upgradedHashes
