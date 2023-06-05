# -*- test-case-name: klein.storage.test.test_common -*-
"""
Glue that connects the SQL DAL to Klein's session interfaces.
"""

from __future__ import annotations

from binascii import hexlify
from dataclasses import dataclass, field
from os import urandom
from time import time
from typing import (
    Any,
    Awaitable,
    Callable,
    Generic,
    Iterable,
    Optional,
    Sequence,
    Type,
    TypeVar,
)
from uuid import uuid4

from attrs import define
from zope.interface import implementer

from twisted.internet.defer import Deferred, gatherResults, succeed
from twisted.python.modules import getModule
from twisted.web.iweb import IRequest

from klein.interfaces import (
    ISession,
    ISessionProcurer,
    ISimpleAccountBinding,
    NoSuchSession,
    SessionMechanism,
)

from ... import SessionProcurer
from ..._isession import AuthorizationMap
from ..._typing_compat import Protocol
from ..._util import eagerDeferredCoroutine
from ...interfaces import ISessionStore, ISimpleAccount
from ..dbxs.dbapi_async import AsyncConnectable, AsyncConnection, transaction
from ..passwords import PasswordEngine, defaultSecureEngine
from ._sql_dal import AccountRecord, SessionDAL, SessionDB, SessionRecord
from ._transactions import requestBoundTransaction


T = TypeVar("T")


@implementer(ISession)
@define
class SQLSession:
    _sessionStore: SessionStore
    identifier: str
    isConfidential: bool
    authenticatedBy: SessionMechanism

    @eagerDeferredCoroutine
    async def authorize(
        self, interfaces: Iterable[Type[object]]
    ) -> AuthorizationMap:
        """
        Authorize all the given interfaces and return a mapping that contains
        all the ones that could be authorized.
        """
        authTypes = set(interfaces)
        result: AuthorizationMap
        result = {}  # type: ignore[assignment]
        # ^ mypy really wants this container to be homogenous along some axis,
        # so a dict with value types that depend on keys doesn't look right to
        # it.
        txn = self._sessionStore._transaction
        store = self._sessionStore

        async def doAuthorize(a: SQLAuthorizer[T]) -> None:
            result[a.authorizationType] = await a.authorizationForSession(
                store, txn, self
            )

        await gatherResults(
            [
                Deferred.fromCoroutine(doAuthorize(each))
                for each in self._sessionStore._authorizers
                if each.authorizationType in authTypes
            ]
        )
        return result

    @classmethod
    def realize(
        cls,
        record: SessionRecord,
        store: SessionStore,
        authenticatedBy: SessionMechanism,
    ) -> SQLSession:
        """
        Construct a 'live' session with authentication information and a store
        with authorizers from a session record.
        """
        return cls(
            sessionStore=store,
            authenticatedBy=authenticatedBy,
            isConfidential=record.confidential,
            identifier=record.session_id,
        )


@implementer(ISessionStore)
@define
class SessionStore:
    """
    An implementation of L{ISessionStore} based on an L{AsyncConnection}, that
    stores sessions in a database.
    """

    _transaction: AsyncConnection
    _authorizers: Sequence[SQLAuthorizer[object]]
    _passwordEngine: PasswordEngine

    @property
    def db(self) -> SessionDAL:
        """
        return database wrapper
        """
        return SessionDB(self._transaction)

    async def _sentInsecurely(self, tokens: Sequence[str]) -> None:
        """
        Tokens have been sent insecurely; delete any tokens expected to be
        confidential.  Return a deferred that fires when they've been deleted.

        @param tokens: L{list} of L{str}

        @return: a L{Deferred} that fires when the tokens have been
            invalidated.
        """
        for token in tokens:
            await self.db.deleteSession(token)

    def sentInsecurely(self, tokens: Sequence[str]) -> None:
        """
        Per the interface, fire-and-forget version of _sentInsecurely
        """
        Deferred.fromCoroutine(self._sentInsecurely(tokens))

    @eagerDeferredCoroutine
    async def newSession(
        self, isConfidential: bool, authenticatedBy: SessionMechanism
    ) -> ISession:
        identifier = hexlify(urandom(32)).decode("ascii")
        await self.db.insertSession(
            identifier, isConfidential, time(), authenticatedBy.name
        )
        result = SQLSession(
            self,
            identifier=identifier,
            isConfidential=isConfidential,
            authenticatedBy=authenticatedBy,
        )
        return result

    @eagerDeferredCoroutine
    async def loadSession(
        self,
        identifier: str,
        isConfidential: bool,
        authenticatedBy: SessionMechanism,
    ) -> ISession:
        record = await self.db.sessionByID(
            identifier, isConfidential, authenticatedBy.name
        )
        if record is None:
            raise NoSuchSession("session not found")
        return SQLSession.realize(record, self, authenticatedBy)


@implementer(ISimpleAccount)
@dataclass
class SQLAccount:
    """
    SQL-backed implementation of ISimpleAccount
    """

    _store: SessionStore
    _record: AccountRecord

    @property
    def accountID(self) -> str:
        return self._record.accountID

    @eagerDeferredCoroutine
    async def bindSession(self, session: ISession) -> None:
        return await self._record.bindSession(session)

    @eagerDeferredCoroutine
    async def changePassword(self, newPassword: str) -> None:
        """
        @param newPassword: The text of the new password.
        @type newPassword: L{unicode}
        """
        computedHash = await self._store._passwordEngine.computeKeyText(
            newPassword
        )
        await self._record.db.resetPassword(self.accountID, computedHash)

    @property
    def username(self) -> str:
        return self._record.username


@implementer(ISimpleAccountBinding)
@define
class AccountSessionBinding:
    """
    (Stateless) binding between an account and a session, so that sessions can
    attach to and detach from authenticated account objects.
    """

    _store: SessionStore
    _session: ISession
    _transaction: AsyncConnection

    def _account(self, accountID: str, username: str, email: str) -> SQLAccount:
        """
        Construct an L{SQLAccount} bound to this plugin & dataStore.
        """
        return SQLAccount(
            self._store, AccountRecord(self.db, accountID, username, email)
        )

    @property
    def db(self) -> SessionDAL:
        """
        session db
        """
        return SessionDB(self._transaction)

    @eagerDeferredCoroutine
    async def createAccount(
        self, username: str, email: str, password: str
    ) -> Optional[ISimpleAccount]:
        """
        Create a new account with the given username, email and password.

        @return: an L{Account} if one could be created, L{None} if one could
            not be.
        """
        computedHash = await self._store._passwordEngine.computeKeyText(
            password
        )
        newAccountID = str(uuid4())
        try:
            await self.db.createAccount(
                newAccountID, username, email, computedHash
            )
        except Exception:
            # TODO: wrap up IntegrityError from DB binding somehow so we can be
            # more selective about what we're catching.
            return None
        else:
            accountID = newAccountID
        account = self._account(accountID, username, email)
        return account

    @eagerDeferredCoroutine
    async def bindIfCredentialsMatch(
        self, username: str, password: str
    ) -> Optional[ISimpleAccount]:
        """
        Associate this session with a given user account, if the password
        matches.

        @param username: The username input by the user.

        @param password: The plain-text password input by the user.
        """
        maybeAccountRecord = await self.db.accountByUsername(username)
        if maybeAccountRecord is None:
            return None

        accountRecord = maybeAccountRecord

        def storeNewBlob(newPWText: str) -> Any:
            return self.db.resetPassword(accountRecord.accountID, newPWText)

        assert accountRecord.password_blob is not None
        if await self._store._passwordEngine.checkAndReset(
            accountRecord.password_blob,
            password,
            storeNewBlob,
        ):
            account = SQLAccount(self._store, accountRecord)
            await account.bindSession(self._session)
            return account
        return None

    @eagerDeferredCoroutine
    async def boundAccounts(self) -> Sequence[ISimpleAccount]:
        """
        Retrieve the accounts currently associated with this session.

        @return: L{Deferred} firing with a L{list} of accounts.
        """
        accounts = []
        async for record in self.db.boundAccounts(self._session.identifier):
            accounts.append(SQLAccount(self._store, record))
        return accounts

    @eagerDeferredCoroutine
    async def unbindThisSession(self) -> None:
        """
        Disassociate this session from any accounts it's logged in to.

        @return: a L{Deferred} that fires when the account is logged out.
        """
        await self.db.unbindSession(self._session.identifier)


@implementer(ISessionProcurer)
@dataclass
class SQLSessionProcurer:
    """
    Alternate implementation of L{ISessionProcurer}, necessary because the
    underlying L{SessionProcurer} requires an L{ISessionStore}, and our
    L{ISessionStore} implementation requires a database transaction to be
    associated with both it and the request.
    """

    connectable: AsyncConnectable
    authorizers: Sequence[SQLAuthorizer[Any]]
    passwordEngine: PasswordEngine = field(default_factory=defaultSecureEngine)
    storeToProcurer: Callable[
        [ISessionStore], SessionProcurer
    ] = SessionProcurer

    @eagerDeferredCoroutine
    async def procureSession(
        self, request: IRequest, forceInsecure: bool = False
    ) -> ISession:
        """
        Procure a session from the underlying procurer, keeping track of the IP
        of the request object.
        """
        alreadyProcured: Optional[ISession] = ISession(request, None)

        assert (
            alreadyProcured is None
        ), """
        Sessions should only be procured once during the lifetime of the
        request, and it should not be possible to invoke procureSession
        multiple times when getting them from dependency injection.
        """

        # Deferred is declared as contravariant, but this is an error, it
        # really ought to be covariant (like Awaitable)
        allAuthorizers: Sequence[SQLAuthorizer[Any]] = [
            simpleAccountBinding.authorizer,
            logMeIn.authorizer,
            *self.authorizers,
        ]
        transaction = await requestBoundTransaction(request, self.connectable)
        procurer = self.storeToProcurer(
            SessionStore(transaction, allAuthorizers, self.passwordEngine)
        )
        return await procurer.procureSession(request, forceInsecure)


_authorizerFunction = Callable[
    [SessionStore, AsyncConnection, ISession], "Awaitable[Optional[T]]"
]


class _FunctionWithAuthorizer(Protocol[T]):
    authorizer: SQLAuthorizer[T]
    authorizerType: Type[T]

    def __call__(
        self,
        sessionStore: SessionStore,
        transaction: AsyncConnection,
        session: ISession,
    ) -> Deferred[T]:
        """
        Signature for a function that can have an authorizer attached to it.
        """


@define
class SQLAuthorizer(Generic[T]):
    authorizationType: Type[T]
    _decorated: _authorizerFunction[T]

    def authorizationForSession(
        self,
        sessionStore: SessionStore,
        transaction: AsyncConnection,
        session: ISession,
    ) -> Awaitable[Optional[T]]:
        return self._decorated(sessionStore, transaction, session)


def authorizerFor(
    authorizationType: Type[T],
) -> Callable[[_authorizerFunction[T]], _FunctionWithAuthorizer[T]]:
    """
    Declare an authorizer.
    """

    def decorator(
        decorated: _authorizerFunction[T],
    ) -> _FunctionWithAuthorizer[T]:
        result: _FunctionWithAuthorizer = decorated  # type:ignore[assignment]
        result.authorizer = SQLAuthorizer[T](authorizationType, decorated)
        result.authorizerType = authorizationType
        return result

    return decorator


@authorizerFor(ISimpleAccountBinding)
def simpleAccountBinding(
    sessionStore: SessionStore,
    transaction: AsyncConnection,
    session: ISession,
) -> Deferred[ISimpleAccountBinding]:
    """
    All sessions are authorized for access to an L{ISimpleAccountBinding}.
    """
    return succeed(AccountSessionBinding(sessionStore, session, transaction))


@authorizerFor(ISimpleAccount)
async def logMeIn(
    sessionStore: ISessionStore,
    transaction: AsyncConnection,
    session: ISession,
) -> Optional[ISimpleAccount]:
    """
    Retrieve an L{ISimpleAccount} authorization.
    """
    binding = (await session.authorize([ISimpleAccountBinding]))[
        ISimpleAccountBinding
    ]
    accounts = await binding.boundAccounts()
    for account in accounts:
        return account
    return None


async def applyBasicSchema(connectable: AsyncConnectable) -> None:
    """
    Apply the session and authentication schema to the given database within a
    dedicated transaction.
    """
    async with transaction(connectable) as c:
        cursor = await c.cursor()
        for stmt in (
            getModule(__name__)
            .filePath.parent()
            .parent()
            .child("sql")
            .child("basic_auth_schema.sql")
            .getContent()
            .decode("utf-8")
            .split(";")
        ):
            await cursor.execute(stmt)
