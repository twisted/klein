# -*- test-case-name: klein.storage.passwords.test.test_passwords -*-
from __future__ import annotations

from dataclasses import dataclass
from os import urandom
from re import compile as compileRE
from typing import TYPE_CHECKING, Awaitable, Callable, Type
from unicodedata import normalize

from ..._util import threadedDeferredFunction
from ._interfaces import PasswordEngine


try:
    from hashlib import scrypt
except ImportError:
    # PyPy ships without scrypt so we need cryptography there.
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

    # The signature of C{scrypt} from the standard library has a bunch of
    # additional complexity, supporting memory views and types other than
    # `bytes`, but this is not a publicly exposed or particularly principled
    # annotation so we ignore the minor differences in the two signatures here.

    def scrypt(  # type:ignore[misc]
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


def defaultSecureEngine() -> PasswordEngine:
    """
    Supply an implementation to the caller of L{PasswordEngine} suitable for
    deployment to production.

    Presently this is an C{scrypt}-based implementation using cost parameters
    recommended by OWASP as this is a least-common-denominator approach.

    However, this entrypoint is guaranteed to return a L{PasswordEngine} in the
    future that can backward-compatibly parse outputs from C{computeKeyText}
    and C{checkAndReset} from any previous version of Klein, as well as store
    upgraded hashes whenever modern security standards are upgraded.

    @see: for testing, use L{klein.storage.passwords.testing.engineForTesting}.
    """
    return KleinV1PasswordEngine()


if TYPE_CHECKING:
    _1: Type[PasswordEngine] = KleinV1PasswordEngine
