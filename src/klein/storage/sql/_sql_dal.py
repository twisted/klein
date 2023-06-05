# -*- test-case-name: klein.storage.sql.test,klein.storage.test.test_common -*-
from __future__ import annotations

from datetime import datetime
from typing import AsyncIterable, Optional

from attrs import define

from ..._typing_compat import Protocol
from ..._util import eagerDeferredCoroutine
from ...interfaces import ISession
from ..dbxs import accessor, many, maybe, query, statement


@define
class SessionRecord:
    """
    The fields from the session that are stored in the database.

    The distinction between a L{SessionRecord} and an L{SQLSession} is that an
    L{SQLSession} binds to an actual request, and thus has an
    C{authenticatedBy} attribute, which inherently cannot be stored in the
    database.
    """

    db: SessionDAL
    session_id: str
    confidential: bool


@define
class AccountRecord:
    """
    An implementation of L{ISimpleAccount} backed by an SQL data store.
    """

    db: SessionDAL
    accountID: str
    username: str
    email: str
    password_blob: Optional[str] = None

    @eagerDeferredCoroutine
    async def bindSession(self, session: ISession) -> None:
        """
        Add a session to the database.
        """
        await self.db.bindAccountToSession(self.accountID, session.identifier)


class SessionDAL(Protocol):
    """
    Data access layer for core sessions database.
    """

    @statement(
        sql="delete from session where "
        "session_id = {session_id} and "
        "confidential = true"
    )
    async def deleteSession(self, session_id: str) -> None:
        """
        Signature for deleting a session by session ID.
        """

    @statement(sql="insert into session values ({session_id}, {confidential})")
    async def insertSession(self, session_id: str, confidential: bool) -> None:
        """
        Signature for deleting a session by session ID.
        """

    @query(
        sql=(
            "select session_id, confidential from session "
            "where session_id = {session_id} and "
            "confidential = {is_confidential}"
        ),
        load=maybe(SessionRecord),
    )
    async def sessionByID(
        self, session_id: str, is_confidential: bool
    ) -> Optional[SessionRecord]:
        """
        Signature for getting a session by session ID.
        """

    @statement(
        sql="insert into account values "
        "({account_id}, {username}, {email}, {password_blob})"
    )
    async def createAccount(
        self, account_id: str, username: str, email: str, password_blob: str
    ) -> None:
        """
        Signature for creating an account.
        """

    @statement(
        sql="insert into session_account values ({account_id}, {session_id})"
    )
    async def bindAccountToSession(
        self, account_id: str, session_id: str
    ) -> None:
        """
        Signature for binding an account to a session.
        """

    @query(
        sql=(
            "select account_id, username, email, password_blob "
            "from account "
            "where username = {username}"
        ),
        load=maybe(AccountRecord),
    )
    async def accountByUsername(self, username: str) -> Optional[AccountRecord]:
        """
        Load an account by username.
        """

    @statement(
        sql="""
        update account
            set password_blob = {newBlob}
        where account_id = {accountID}
        """
    )
    async def resetPassword(self, accountID: str, newBlob: str) -> None:
        """
        Reset the password for the given account ID.
        """

    @query(
        sql="""
        select account.account_id,
               account.username,
               account.email,
               account.password_blob
        from session_account
            join account
        where session_account.session_id = {session_id}
              and session_account.account_id = account.account_id
        """,
        load=many(AccountRecord),
    )
    def boundAccounts(self, session_id: str) -> AsyncIterable[AccountRecord]:
        """
        Load all account objects bound to the given session id.
        """

    @statement(
        sql="""
        delete from session_account where session_id = {sessionID}
        """
    )
    async def unbindSession(self, sessionID: str) -> None:
        """
        Un-bind the given session from the account it's currently bound to.
        """

    @statement(
        sql="""
        insert into session_ip values (
            {sessionID}, {ipAddress}, {addressFamily}, {lastUsed}
        )
        on conflict(session_id, ip_address, address_family)
        do update set last_used = excluded.last_used
        """,
    )
    async def createOrUpdateIPRecord(
        self,
        sessionID: str,
        ipAddress: str,
        addressFamily: str,
        lastUsed: datetime,
    ) -> None:
        """
        Add the given IP or update its last-used timestamp.
        """


SessionDB = accessor(SessionDAL)
