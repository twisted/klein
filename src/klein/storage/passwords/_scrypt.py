# -*- test-case-name: klein.storage.passwords.test.test_passwords -*-
from __future__ import annotations

from dataclasses import dataclass, field
from os import urandom
from re import compile as compileRE
from typing import TYPE_CHECKING, Awaitable, Callable, Optional, Type
from unicodedata import normalize


if TYPE_CHECKING:
    from unittest import TestCase

try:
    from hashlib import scrypt
except ImportError:
    if not TYPE_CHECKING:
        # PyPy ships without scrypt so we need cryptography there.  There are a
        # bunch of spurious type-checking issues here, like the signature not
        # matching due to weird extra buffer types in the stdlib and not having
        # the `cryptography` stubs available in our typechecking environment,
        # so we'll just ignore it.
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

        def scrypt(
            password: bytes,
            *,
            salt: bytes,
            n: int,
            r: int,
            p: int,
            maxmem: int = 0,
            dklen: int = 64,
        ) -> bytes:
            return Scrypt(salt=salt, length=dklen, n=n, r=r, p=p).derive(
                password
            )


from hashlib import sha256

from klein._typing_compat import Protocol
from klein._util import threadedDeferredFunction


@threadedDeferredFunction
def runScrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    """
    Run L{scrypt} in a thread.
    """
    maxmem = (2**8) * n * r
    return scrypt(
        normalize("NFD", password).encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        maxmem=maxmem,
    )


class InvalidPasswordRecord(Exception):
    """
    A stored password was not in a valid format.
    """


sep = "\\$"
MARKER = "klein-scrypt"


HEX = "[0-9a-f]+"
INT = "[0-9]+"


def g(**names: str) -> str:
    [[name, expression]] = list(names.items())
    return f"(?P<{name}>{expression})"


fields = [MARKER, g(hashed=HEX), g(salt=HEX), g(n=INT), g(r=INT), g(p=INT)]
recordRE = compileRE(sep + sep.join(fields) + sep)


@dataclass
class SCryptHashedPassword:
    """
    a password hashed using SCrypt with certain parameters.
    """

    hashed: bytes
    salt: bytes
    n: int
    r: int
    p: int

    def serialize(self) -> str:
        """
        Serialize this L{SCryptHashedPassword} to a string.  Callers must
        consider this opaque.
        """
        return (
            f"${MARKER}${self.hashed.hex()}"
            f"${self.salt.hex()}${self.n}${self.r}${self.p}$"
        )

    async def verify(self, password: str) -> bool:
        """
        Compare the given password to this hash.

        @return: an awaitable True if it matches, False if it doesn't.
        """
        computed = await runScrypt(password, self.salt, self.n, self.r, self.p)
        return self.hashed == (computed)

    @classmethod
    def load(cls, serialized: str) -> SCryptHashedPassword:
        """
        Load a SCryptHashedPassword from a string produced by
        L{SCryptHashedPassword.serialize}.
        """
        matched = recordRE.fullmatch(serialized)
        if not matched:
            raise InvalidPasswordRecord("invalid password record")
        return cls(
            bytes.fromhex(matched["hashed"]),
            bytes.fromhex(matched["salt"]),
            int(matched["n"]),
            int(matched["r"]),
            int(matched["p"]),
        )

    @classmethod
    # "If Argon2id is not available, use scrypt with a minimum CPU/memory cost
    # parameter of (2^17), a minimum block size of 8 (1024 bytes), and a
    # parallelization parameter of 1." -
    # https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
    async def new(
        cls, inputText: str, n: int = 2**18, r: int = 8, p: int = 1
    ) -> SCryptHashedPassword:
        """
        Hash C{inputText} in a thread to create a new L{SCryptHashedPassword}.
        """
        salt = urandom(16)
        return cls(await runScrypt(inputText, salt, n, r, p), salt, n, r, p)


class PasswordEngine(Protocol):
    """
    Interface required to hash passwords for secure storage.
    """

    async def computeKeyText(
        self,
        passwordText: str,
    ) -> str:
        """
        Compute some text to store for a given plain-text password.

        @param passwordText: The text of a new password, as entered by a user.

        @return: The hashed text to store.
        """

    async def checkAndReset(
        self,
        storedPasswordHash: str,
        providedPasswordText: str,
        storeNewHash: Callable[[str], Awaitable[None]],
    ) -> bool:
        """
        Check the given stored password text against the given provided
        password text.  If password policies have changed since the given hash
        was stored and C{providedPasswordText} is correct, compute a new hash
        and use C{storeNewHash} to write it back to the data store.

        @param storedPasswordText: the opaque hashed output from our hash
            function, stored in a datastore.

        @param providedPasswordText: the plain-text password provided by the
            user.

        @param storeNewHash: A function that stores a new hash in the database.

        @return: an awaitable boolean; C{True} if the password matches (i.e,
            the user has successfully authenticated) and C{False} if the
            password does not match.
        """


@dataclass
class KleinV1PasswordEngine:
    """
    Built-in engine for hashing passwords for secure storage with basic
    C{scrypt} parameters.

    Implementation of L{PasswordEngine}.
    """

    minimumN: int = 2**18
    preferredN: int = 2**19

    async def computeKeyText(self, passwordText: str) -> str:
        hashed = await SCryptHashedPassword.new(passwordText, self.preferredN)
        return hashed.serialize()

    async def checkAndReset(
        self,
        storedPasswordHash: str,
        providedPasswordText: str,
        storeNewHash: Callable[[str], Awaitable[None]],
    ) -> bool:
        hashed = SCryptHashedPassword.load(storedPasswordHash)
        if await hashed.verify(providedPasswordText):
            if hashed.n < self.minimumN:
                newHash = await SCryptHashedPassword.new(
                    providedPasswordText, self.preferredN
                )
                await storeNewHash(newHash.serialize())
            return True
        else:
            return False


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
            await storeNewHash(newVersion)
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


if TYPE_CHECKING:
    _1: Type[PasswordEngine] = KleinV1PasswordEngine
