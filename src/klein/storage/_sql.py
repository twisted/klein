from binascii import hexlify
from datetime import datetime
from functools import reduce
from os import urandom
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Type,
    TypeVar,
    cast,
)
from uuid import uuid4

import attr
from attr import Factory
from attr.validators import instance_of as an
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    MetaData,
    Table,
    Unicode,
    UniqueConstraint,
    true,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable
from sqlalchemy.sql.expression import select
from zope.interface import implementer
from zope.interface.interfaces import IInterface

from twisted.internet.defer import (
    gatherResults,
    inlineCallbacks,
    maybeDeferred,
    returnValue,
)
from twisted.python.compat import unicode

from .. import SessionProcurer
from ..interfaces import (
    ISession,
    ISessionProcurer,
    ISessionStore,
    ISimpleAccount,
    ISimpleAccountBinding,
    NoSuchSession,
    SessionMechanism,
)
from ._security import checkAndReset, computeKeyText
from ._sql_generic import Transaction, requestBoundTransaction
from .interfaces import ISQLAuthorizer


if TYPE_CHECKING:  # pragma: no cover
    import sqlalchemy

    from twisted.internet.defer import Deferred
    from twisted.internet.interfaces import IReactorThreads
    from twisted.web.iweb import IRequest

    from ._sql_generic import DataStore

    (
        Any,
        Callable,
        Deferred,
        Type,
        Iterable,
        IReactorThreads,
        str,
        List,
        sqlalchemy,
        Dict,
        IRequest,
        IInterface,
        Optional,
        DataStore,
    )
    T = TypeVar("T")


@implementer(ISession)
@attr.s
class SQLSession:
    _sessionStore = attr.ib(type="SessionStore")
    identifier = attr.ib(type=str)
    isConfidential = attr.ib(type=bool)
    authenticatedBy = attr.ib(type=SessionMechanism)

    def authorize(self, interfaces):
        # type: (Iterable[IInterface]) -> Any
        interfaces = set(interfaces)
        result = {}  # type: Dict[IInterface, Deferred]
        ds = []  # type: List[Deferred]
        txn = self._sessionStore._transaction
        for a in self._sessionStore._authorizers:
            # This should probably do something smart with interface
            # priority, checking isOrExtends or something similar.
            if a.authorizationInterface in interfaces:
                v = maybeDeferred(
                    a.authorizationForSession, self._sessionStore, txn, self
                )
                ds.append(v)
                result[a.authorizationInterface] = v
                v.addCallback(
                    lambda value, ai: result.__setitem__(ai, value),
                    ai=a.authorizationInterface,
                )

        def r(ignored):
            # type: (T) -> Dict[str, Any]
            return result

        return gatherResults(ds).addCallback(r)


@attr.s
class SessionIPInformation:
    """
    Information about a session being used from a given IP address.
    """

    id = attr.ib(validator=an(str), type=str)
    ip = attr.ib(validator=an(str), type=str)
    when = attr.ib(validator=an(datetime), type=datetime)


@implementer(ISessionStore)
@attr.s()
class SessionStore:
    """
    An implementation of L{ISessionStore} based on a L{DataStore}, that
    stores sessions in a SQLAlchemy database.
    """

    _transaction = attr.ib(type=Transaction)
    _authorizers = attr.ib(type=List[ISQLAuthorizer], default=Factory(list))

    def sentInsecurely(self, tokens):
        # type: (List[str]) -> Deferred
        """
        Tokens have been sent insecurely; delete any tokens expected to be
        confidential.

        @param tokens: L{list} of L{str}

        @return: a L{Deferred} that fires when the tokens have been
            invalidated.
        """
        s = sessionSchema.session
        return gatherResults(
            [
                self._transaction.execute(
                    s.delete().where(
                        (s.c.session_id == token) & (s.c.confidential == true())
                    )
                )
                for token in tokens
            ]
        )

    @inlineCallbacks
    def newSession(self, isConfidential, authenticatedBy):
        # type: (bool, SessionMechanism) -> Deferred
        identifier = hexlify(urandom(32)).decode("ascii")
        s = sessionSchema.session
        yield self._transaction.execute(
            s.insert().values(
                session_id=identifier,
                confidential=isConfidential,
            )
        )
        returnValue(
            SQLSession(
                self,
                identifier=identifier,
                isConfidential=isConfidential,
                authenticatedBy=authenticatedBy,
            )
        )

    @inlineCallbacks
    def loadSession(self, identifier, isConfidential, authenticatedBy):
        # type: (Text, bool, SessionMechanism) -> Deferred
        s = sessionSchema.session
        result = yield self._transaction.execute(
            s.select(
                (s.c.session_id == identifier)
                & (s.c.confidential == isConfidential)
            )
        )
        results = yield result.fetchall()
        if not results:
            raise NoSuchSession("Session not present in SQL store.")
        fetched_identifier = results[0][s.c.session_id]
        returnValue(
            SQLSession(
                self,
                identifier=fetched_identifier,
                isConfidential=isConfidential,
                authenticatedBy=authenticatedBy,
            )
        )


@implementer(ISimpleAccountBinding)
@attr.s
class AccountSessionBinding:
    """
    (Stateless) binding between an account and a session, so that sessions can
    attach to, detach from, .
    """

    _session = attr.ib(type=ISession)
    _transaction = attr.ib(type=Transaction)

    def _account(self, accountID, username, email):
        # type: (Text, Text, Text) -> SQLAccount
        """
        Construct an L{SQLAccount} bound to this plugin & dataStore.
        """
        return SQLAccount(self._transaction, accountID, username, email)

    @inlineCallbacks
    def createAccount(self, username, email, password):
        # type: (Text, Text, Text) -> Any
        """
        Create a new account with the given username, email and password.

        @return: an L{Account} if one could be created, L{None} if one could
            not be.
        """
        computedHash = yield computeKeyText(password)
        newAccountID = unicode(uuid4())
        insert = sessionSchema.account.insert().values(
            account_id=newAccountID,
            username=username,
            email=email,
            password_blob=computedHash,
        )
        try:
            yield self._transaction.execute(insert)
        except IntegrityError:
            returnValue(None)
        else:
            accountID = newAccountID
        account = self._account(accountID, username, email)
        returnValue(account)

    @inlineCallbacks
    def bindIfCredentialsMatch(self, username, password):
        # type: (Text, Text) -> Any
        """
        Associate this session with a given user account, if the password
        matches.

        @param username: The username input by the user.
        @type username: L{text_type}

        @param password: The plain-text password input by the user.
        @type password: L{text_type}

        @rtype: L{Deferred} firing with L{IAccount} if we succeeded and L{None}
            if we failed.
        """
        acc = sessionSchema.account

        result = yield self._transaction.execute(
            acc.select(acc.c.username == username)
        )
        accountsInfo = yield result.fetchall()
        if not accountsInfo:
            # no account, bye
            returnValue(None)
        [row] = accountsInfo
        stored_password_text = row[acc.c.password_blob]
        accountID = row[acc.c.account_id]

        def reset_password(newPWText):
            # type: (Text) -> Any
            a = sessionSchema.account
            return self._transaction.execute(
                a.update(a.c.account_id == accountID).values(
                    password_blob=newPWText
                )
            )

        if (
            yield checkAndReset(stored_password_text, password, reset_password)
        ):
            account = self._account(
                accountID, row[acc.c.username], row[acc.c.email]
            )
            yield account.bindSession(self._session)
            returnValue(account)

    @inlineCallbacks
    def boundAccounts(self):
        # type: () -> Deferred
        """
        Retrieve the accounts currently associated with this session.

        @return: L{Deferred} firing with a L{list} of accounts.
        """
        ast = sessionSchema.sessionAccount
        acc = sessionSchema.account
        result = yield (
            yield self._transaction.execute(
                ast.join(acc, ast.c.account_id == acc.c.account_id).select(
                    ast.c.session_id == self._session.identifier,
                    use_labels=True,
                )
            )
        ).fetchall()
        returnValue(
            [
                self._account(
                    it[ast.c.account_id], it[acc.c.username], it[acc.c.email]
                )
                for it in result
            ]
        )

    @inlineCallbacks
    def boundSessionInformation(self):
        # type: () -> Any
        """
        Retrieve information about all sessions attached to the same account
        that this session is.

        @return: L{Deferred} firing a L{list} of L{SessionIPInformation}
        """
        acs = sessionSchema.sessionAccount
        sipt = sessionSchema.sessionIP

        acs2 = acs.alias()
        result = yield self._transaction.execute(
            select([sipt], use_labels=True).where(
                (acs.c.session_id == self._session.identifier)
                & (acs.c.account_id == acs2.c.account_id)
                & (acs2.c.session_id == sipt.c.session_id)
            )
        )
        returnValue(
            [
                SessionIPInformation(
                    id=row[sipt.c.session_id],
                    ip=row[sipt.c.ip_address],
                    when=row[sipt.c.last_used],
                )
                for row in (yield result.fetchall())
            ]
        )

    def unbindThisSession(self):
        # type: () -> Any
        """
        Disassociate this session from any accounts it's logged in to.

        @return: a L{Deferred} that fires when the account is logged out.
        """
        ast = sessionSchema.sessionAccount
        return self._transaction.execute(
            ast.delete(ast.c.session_id == self._session.identifier)
        )


@implementer(ISimpleAccount)
@attr.s
class SQLAccount:
    """
    An implementation of L{ISimpleAccount} backed by an Alchimia data store.
    """

    _transaction = attr.ib(type=Transaction)
    accountID = attr.ib(type=str)
    username = attr.ib(type=str)
    email = attr.ib(type=str)

    def bindSession(self, session):
        # type: (ISession) -> Deferred
        """
        Add a session to the database.
        """
        return self._transaction.execute(
            sessionSchema.sessionAccount.insert().values(
                account_id=self.accountID, session_id=session.identifier
            )
        )

    @inlineCallbacks
    def changePassword(self, newPassword):
        # type: (Text) -> Any
        """
        @param newPassword: The text of the new password.
        @type newPassword: L{unicode}
        """
        computedHash = yield computeKeyText(newPassword)
        result = yield self._transaction.execute(
            sessionSchema.account.update()
            .where(account_id=self.accountID)
            .values(password_blob=computedHash)
        )
        returnValue(result)


@inlineCallbacks
def upsert(
    engine,  # type: Transaction
    table,  # type: sqlalchemy.schema.Table
    to_query,  # type: Dict[str, Any]
    to_change,  # type: Dict[str, Any]
):
    # type: (...) -> Any
    """
    Try inserting, if inserting fails, then update.
    """
    try:
        result = yield engine.execute(
            table.insert().values(**dict(to_query, **to_change))
        )
    except IntegrityError:
        from operator import and_ as And

        update = (
            table.update()
            .where(
                reduce(
                    And,
                    (
                        (getattr(table.c, cname) == cvalue)
                        for (cname, cvalue) in to_query.items()
                    ),
                )
            )
            .values(**to_change)
        )
        result = yield engine.execute(update)
    returnValue(result)


@attr.s
class SessionSchema:
    """
    Schema for SQL session features.

    This is exposed as public API so that you can have tables which relate
    against it in your own code, and integrate with your schema management
    system.

    However, while Klein uses Alchimia itself, it does not want to be in the
    business of managing your schema migrations or your database access.  As
    such, this class exposes the schema in several formats:

        - via SQLAlchemy metadata, if you want to use something like Alembic or
          SQLAlchemy-Migrate

        - via a single SQL string, if you manage your SQL migrations manually
    """

    session = attr.ib(type=Table)
    account = attr.ib(type=Table)
    sessionAccount = attr.ib(type=Table)
    sessionIP = attr.ib(type=Table)

    @classmethod
    def withMetadata(cls, metadata=None):
        # type: (Optional[MetaData]) -> SessionSchema
        """
        Create a new L{SQLSessionSchema} with the given metadata, defaulting to
        new L{MetaData} if none is supplied.
        """
        if metadata is None:
            metadata = MetaData()
        session = Table(
            "session",
            metadata,
            Column("session_id", Unicode(), primary_key=True, nullable=False),
            Column("confidential", Boolean(), nullable=False),
        )
        account = Table(
            "account",
            metadata,
            Column("account_id", Unicode(), primary_key=True, nullable=False),
            Column("username", Unicode(), unique=True, nullable=False),
            Column("email", Unicode(), nullable=False),
            Column("password_blob", Unicode(), nullable=False),
        )
        sessionAccount = Table(
            "session_account",
            metadata,
            Column(
                "account_id",
                Unicode(),
                ForeignKey(account.c.account_id, ondelete="CASCADE"),
            ),
            Column(
                "session_id",
                Unicode(),
                ForeignKey(session.c.session_id, ondelete="CASCADE"),
            ),
            UniqueConstraint("account_id", "session_id"),
        )
        sessionIP = Table(
            "session_ip",
            metadata,
            Column(
                "session_id",
                Unicode(),
                ForeignKey(session.c.session_id, ondelete="CASCADE"),
            ),
            Column("ip_address", Unicode(), nullable=False),
            Column("address_family", Unicode(), nullable=False),
            Column("last_used", DateTime(), nullable=False),
            UniqueConstraint("session_id", "ip_address", "address_family"),
        )
        return cls(session, account, sessionAccount, sessionIP)

    def tables(self):
        # type: () -> Iterable[Table]
        """
        Yield all tables that need to be created in order for sessions to be
        enabled in a SQLAlchemy database, in the order they need to be created.
        """
        yield self.session
        yield self.account
        yield self.sessionAccount
        yield self.sessionIP

    @inlineCallbacks
    def create(self, transaction):
        # type: (Transaction) -> Deferred
        """
        Given a L{Transaction}, create this schema in the database and return a
        L{Deferred} that fires with C{None} when done.

        This method will handle any future migration concerns.
        """
        for table in self.tables():
            yield transaction.execute(CreateTable(table))

    def migrationSQL(self):
        # type: () -> Text
        """
        Return some SQL to run in order to create the tables necessary for the
        SQL session and account store.  Currently there is only one version,
        but in the future, sections of this will be clearly delineated by '--
        Klein Session Schema Version X' comments.

        This SQL will not attempt to discern whether the tables exist already
        or whether the migrations should be run.
        """
        return "\n-- Klein Session Schema Version 1\n" + (
            ";".join(str(CreateTable(table)) for table in self.tables())
        )


sessionSchema = SessionSchema.withMetadata(MetaData())

procurerFromTransactionT = Callable[[Transaction], ISessionProcurer]


@implementer(ISessionProcurer)
class IPTrackingProcurer:
    """
    An implementation of L{ISessionProcurer} that keeps track of the source IP
    of the originating session.
    """

    def __init__(
        self,
        dataStore,  # type: DataStore
        procurerFromTransaction,  # type: procurerFromTransactionT
    ):
        # type: (...) -> None
        """
        Create an L{IPTrackingProcurer} from SQLAlchemy metadata, an alchimia
        data store, and an existing L{ISessionProcurer}.
        """
        self._dataStore = dataStore
        self._procurerFromTransaction = procurerFromTransaction

    @inlineCallbacks
    def procureSession(self, request, forceInsecure=False):
        # type: (IRequest, bool) -> Deferred
        """
        Procure a session from the underlying procurer, keeping track of the IP
        of the request object.
        """
        alreadyProcured = request.getComponent(ISession)
        if alreadyProcured is not None:
            returnValue(alreadyProcured)
        # if getattr(request, 'requesting', False):
        #     raise RuntimeError("what are you doing!?")
        # request.requesting = True
        transaction = yield requestBoundTransaction(request, self._dataStore)
        procurer = yield self._procurerFromTransaction(transaction)
        session = yield procurer.procureSession(request, forceInsecure)
        try:
            ipAddress = (request.client.host or b"").decode("ascii")
        except BaseException:
            ipAddress = ""
        sip = sessionSchema.sessionIP
        yield upsert(
            transaction,
            sip,
            dict(
                session_id=session.identifier,
                ip_address=ipAddress,
                address_family=("AF_INET6" if ":" in ipAddress else "AF_INET"),
            ),
            dict(last_used=datetime.utcnow()),
        )
        # XXX This should set a savepoint because we don't want application
        # logic to be able to roll back the IP access log.
        returnValue(session)


procurerFromStoreT = Callable[[ISessionStore], ISessionProcurer]


def procurerFromDataStore(
    dataStore,  # type: DataStore
    authorizers,  # type: List[ISQLAuthorizer]
    procurerFromStore=SessionProcurer,  # type: procurerFromStoreT
):
    # type: (...) -> ISessionProcurer
    """
    Open a session store, returning a procurer that can procure sessions from
    it.

    @param databaseURL: an SQLAlchemy database URL.

    @param procurerFromStore: A callable that takes an L{ISessionStore} and
        returns an L{ISessionProcurer}.

    @return: L{Deferred} firing with L{ISessionProcurer}
    """
    allAuthorizers = [
        simpleAccountBinding.authorizer,
        logMeIn.authorizer,
    ] + list(authorizers)
    return IPTrackingProcurer(
        dataStore,
        lambda transaction: procurerFromStore(
            SessionStore(transaction, allAuthorizers)
        ),
    )


class _FunctionWithAuthorizer:
    authorizer = None  # type: Any

    def __call__(
        self,
        sessionStore,  # type: SessionStore
        transaction,  # type: Transaction
        session,  # type: ISession
    ):
        # type: (...) -> Any
        """
        Signature for a function that can have an authorizer attached to it.
        """


_authorizerFunction = Callable[[SessionStore, Transaction, ISession], Any]


@implementer(ISQLAuthorizer)
@attr.s
class SimpleSQLAuthorizer:
    authorizationInterface = attr.ib(type=Type)
    _decorated = attr.ib(type=_authorizerFunction)

    def authorizationForSession(self, sessionStore, transaction, session):
        # type: (SessionStore, Transaction, ISession) -> Any
        cb = cast(_authorizerFunction, self._decorated)  # type: ignore
        return cb(sessionStore, transaction, session)


def authorizerFor(
    authorizationInterface,  # type: IInterface
):
    # type: (...) -> Callable[[Callable], _FunctionWithAuthorizer]
    """
    Declare an SQL authorizer, implemented by a given function.  Used like so::

        @authorizerFor(Foo, tables(foo=[Column("bar", Unicode())]))
        def authorizeFoo(dataStore, sessionStore, transaction, session):
            return Foo(metadata, metadata.tables["foo"])

    @param authorizationInterface: The type we are creating an authorizer for.

    @return: a decorator that can decorate a function with the signature
        C{(metadata, dataStore, sessionStore, transaction, session)}
    """

    def decorator(decorated):
        # type: (_authorizerFunction) -> _FunctionWithAuthorizer
        result = cast(_FunctionWithAuthorizer, decorated)
        result.authorizer = SimpleSQLAuthorizer(
            authorizationInterface, decorated
        )
        return result

    return decorator


@authorizerFor(ISimpleAccountBinding)
def simpleAccountBinding(
    sessionStore,  # type: SessionStore
    transaction,  # type: Transaction
    session,  # type: ISession
):
    # type: (...) -> AccountSessionBinding
    """
    All sessions are authorized for access to an L{ISimpleAccountBinding}.
    """
    return AccountSessionBinding(session, transaction)


@authorizerFor(ISimpleAccount)
@inlineCallbacks
def logMeIn(
    sessionStore,  # type: SessionStore
    transaction,  # type: Transaction
    session,  # type: ISession
):
    # type: (...) -> Deferred
    """
    Retrieve an L{ISimpleAccount} authorization.
    """
    binding = (yield session.authorize([ISimpleAccountBinding]))[
        ISimpleAccountBinding
    ]
    returnValue(next(iter((yield binding.boundAccounts())), None))
