# -*- test-case-name: klein.storage.test.test_passwords -*-
from __future__ import annotations

from dataclasses import dataclass


try:
    from hashlib import scrypt
except ImportError:
    # PyPy ships without scrypt so we need cryptography there.
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

    def scrypt(  # type:ignore[misc]
        # these 'bytes' fields are much more complex types with memoryviews and
        # random pickle nonsense in the stdlib.
        password: bytes,
        *,
        salt: bytes,
        n: int,
        r: int,
        p: int,
        maxmem: int = 0,
        dklen: int = 64,
    ) -> bytes:
        return Scrypt(salt=salt, length=dklen, n=n, r=r, p=p).derive(password)


from os import urandom
from typing import TYPE_CHECKING, Callable, ClassVar, Optional, Type
from unicodedata import normalize

from twisted.internet.defer import Deferred

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

    typeCode: ClassVar[str] = "klein-scrypt"

    def serialize(self) -> str:
        """
        Serialize this L{SCryptHashedPassword} to a string.  Callers must
        consider this opaque.
        """
        return (
            f"${self.typeCode}${self.hashed.hex()}"
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
    def load(cls, serialized: str) -> Optional[SCryptHashedPassword]:
        """
        Load a SCryptHashedPassword from a string produced by
        L{SCryptHashedPassword.serialize}.
        """
        fields = serialized.split("$")
        if len(fields) != 8:
            return None
        blank1, pwType, password, salt, n, r, p, blank2 = fields
        if blank1 != "" or blank2 != "" or pwType != cls.typeCode:
            return None
        self = cls(
            bytes.fromhex(password), bytes.fromhex(salt), int(n), int(r), int(p)
        )
        return self

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
        hashedBytes = await runScrypt(inputText, salt, n, r, p)
        self = cls(hashedBytes, salt, n, r, p)
        return self


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

        @return: a L{Deferred} firing with L{unicode}.
        """

    async def checkAndReset(
        self,
        storedPasswordHash: str,
        providedPasswordText: str,
        storeNewHash: Callable[[str], Deferred[None]],
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
    Built-in engine for hashing and storing passwords with basic C{scrypt}
    parameters.
    """

    minimumN: int = 2**18
    preferredN: int = 2**19

    async def computeKeyText(
        self,
        passwordText: str,
    ) -> str:
        return (
            await SCryptHashedPassword.new(passwordText, self.preferredN)
        ).serialize()

    async def checkAndReset(
        self,
        storedPasswordHash: str,
        providedPasswordText: str,
        storeNewHash: Callable[[str], Deferred[None]],
    ) -> bool:
        hashObj = SCryptHashedPassword.load(storedPasswordHash)
        if hashObj is None:
            return False
        if await hashObj.verify(providedPasswordText):
            if hashObj.n < self.minimumN:
                newHash = await SCryptHashedPassword.new(
                    providedPasswordText, self.preferredN
                )
                await storeNewHash(newHash.serialize())
            return True
        else:
            return False


if TYPE_CHECKING:
    _1: Type[PasswordEngine] = KleinV1PasswordEngine
