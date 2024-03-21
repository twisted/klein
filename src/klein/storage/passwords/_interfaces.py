from __future__ import annotations

from typing import Awaitable, Callable

from ..._typing_compat import Protocol


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
