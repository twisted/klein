
from binascii import hexlify
from collections import deque
from datetime import datetime
from functools import reduce
from os import urandom
from typing import (
    Any, Callable, Dict, Iterable, List, TYPE_CHECKING, Text,
    Type, TypeVar, cast
)
from uuid import uuid4

from alchimia import TWISTED_STRATEGY

import attr
from attr import Factory
from attr.validators import instance_of as an

from six import text_type

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, MetaData, Table, Unicode,
    UniqueConstraint, create_engine, true
)
from sqlalchemy.exc import IntegrityError

from twisted.internet.defer import (
    gatherResults, inlineCallbacks, maybeDeferred, returnValue
)
from twisted.python.compat import unicode
from twisted.python.failure import Failure

from zope.interface import implementedBy, implementer
from zope.interface.interfaces import IInterface

from ._security import checkAndReset, computeKeyText
from .. import SessionProcurer
from ..interfaces import (
    ISQLAuthorizer, ISession, ISessionProcurer, ISessionStore, ISimpleAccount,
    ISimpleAccountBinding, NoSuchSession, SessionMechanism, TransactionEnded
)

if TYPE_CHECKING:
    import sqlalchemy
    from twisted.internet.defer import Deferred
    from twisted.internet.interfaces import IReactorThreads
    from twisted.web.iweb import IRequest
    (Any, Callable, Deferred, Type, Iterable, IReactorThreads, Text, List,
     sqlalchemy, Dict, IRequest, IInterface)
    T = TypeVar('T')

@implementer(ISession)
@attr.s
class SQLSession(object):
    _sessionStore = attr.ib(type='AlchimiaSessionStore')
    identifier = attr.ib(type=Text)
    isConfidential = attr.ib(type=bool)
    authenticatedBy = attr.ib(type=SessionMechanism)

    if TYPE_CHECKING:
        def __init__(
                self,
                sessionStore,    # type: AlchimiaSessionStore
                identifier,      # type: Text
                isConfidential,  # type: bool
                authenticatedBy  # type: SessionMechanism
        ):
            # type: (...) -> None
            pass

    def authorize(self, interfaces):
        # type: (Iterable[IInterface]) -> Any
        interfaces = set(interfaces)
        dataStore = self._sessionStore._dataStore

        @dataStore.sql
        def authzn(txn):
            # type: (Transaction) -> Deferred
            result = {}         # type: Dict[IInterface, Deferred]
            ds = []             # type: List[Deferred]
            authorizers = dataStore.componentsProviding(ISQLAuthorizer)
            for a in authorizers:
                # This should probably do something smart with interface
                # priority, checking isOrExtends or something similar.
                if a.authzn_for in interfaces:
                    v = maybeDeferred(a.authzn_for_session,
                                      self._sessionStore, txn, self)
                    ds.append(v)
                    result[a.authzn_for] = v
                    v.addCallback(
                        lambda value, ai: result.__setitem__(ai, value),
                        ai=a.authzn_for
                    )

            def r(ignored):
                # type: (T) -> Dict[str, Any]
                return result
            return (gatherResults(ds).addCallback(r))
        return authzn



@attr.s
class SessionIPInformation(object):
    """
    Information about a session being used from a given IP address.
    """
    id = attr.ib(validator=an(text_type), type=Text)
    ip = attr.ib(validator=an(text_type), type=Text)
    when = attr.ib(validator=an(datetime), type=datetime)

_sqlAlchemyConnection = Any

@attr.s
class Transaction(object):
    """
    Wrapper around a SQLAlchemy connection which is invalidated when the
    transaction is committed or rolled back.
    """
    _connection = attr.ib(type=_sqlAlchemyConnection)
    _stopped = attr.ib(type=Text, default=u"")

    def execute(self, statement, *multiparams, **params):
        # type: (Any, *Any, **Any) -> Deferred
        """
        Execute a statement unless this transaction has been stopped, otherwise
        raise L{TransactionEnded}.
        """
        if self._stopped:
            raise TransactionEnded(self._stopped)
        return self._connection.execute(statement, *multiparams, **params)



@attr.s
class DataStore(object):
    """
    L{DataStore} is a generic storage object that connect to an SQL
    database, run transactions, and manage schema metadata.
    """

    _engine = attr.ib(type=_sqlAlchemyConnection)
    _components = attr.ib(type=List[Any])
    _freeConnections = attr.ib(default=Factory(deque), type=deque)

    @inlineCallbacks
    def sql(self, callable):
        # type: (Callable[[Transaction], Any]) -> Any
        """
        Run the given C{callable}.

        @param callable: A callable object that encapsulates application logic
            that needs to run in a transaction.
        @type callable: callable taking a L{Transaction} and returning a
            L{Deferred}.

        @return: a L{Deferred} firing with the result of C{callable}
        @rtype: L{Deferred} that fires when the transaction is complete, or
            fails when the transaction is rolled back.
        """
        try:
            cxn = (self._freeConnections.popleft() if self._freeConnections
                   else (yield self._engine.connect()))
            sqla_txn = yield cxn.begin()
            txn = Transaction(cxn)
            try:
                result = yield callable(txn)
            except BaseException:
                # XXX rollback() and commit() might both also fail
                failure = Failure()
                txn._stopped = "rolled back"
                yield sqla_txn.rollback()
                returnValue(failure)
            else:
                txn._stopped = "committed"
                yield sqla_txn.commit()
                returnValue(result)
        finally:
            self._freeConnections.append(cxn)


    def componentsProviding(self, interface):
        # type: (Any) -> Iterable[Any]
        # one day: (Type[I]) -> Iterable[I]
        """
        Get all the components providing the given interface.
        """
        for component in self._components:
            if interface.providedBy(component):
                # Adaptation-by-call doesn't work with implementedBy() objects
                # so we can't query for classes
                yield component


    @classmethod
    def open(cls, reactor, dbURL, componentCreators):
        # type: (IReactorThreads, Text, Iterable[Callable]) -> DataStore
        """
        Open an L{DataStore}.

        @param reactor: the reactor that this store should be opened on.
        @type reactor: L{IReactorThreads}

        @param dbURL: the SQLAlchemy database URI to connect to.
        @type dbURL: L{str}

        @param componentCreators: callables which can create components.
        @type componentCreators: C{iterable} of L{callable} taking 2
            arguments; (L{MetaData}, L{DataStore}), and returning a
            non-C{None} value.
        """
        components = []         # type: List[Any]
        self = cls(
            create_engine(dbURL, reactor=reactor, strategy=TWISTED_STRATEGY),
            components,
        )
        components.extend(creator(self) for creator in componentCreators)
        return self


@implementer(ISessionStore)
@attr.s()
class AlchimiaSessionStore(object):
    """
    An implementation of L{ISessionStore} based on an L{AlchimiaStore}, that
    stores sessions in a SQLAlchemy database.
    """

    _dataStore = attr.ib(type=DataStore)

    def sentInsecurely(self, tokens):
        # type: (List[str]) -> Deferred
        """
        Tokens have been sent insecurely; delete any tokens expected to be
        confidential.

        @param tokens: L{list} of L{str}

        @return: a L{Deferred} that fires when the tokens have been
            invalidated.
        """
        @self._dataStore.sql
        def invalidate(txn):
            # type: (Transaction) -> Deferred
            s = sessionSchema.session
            return gatherResults([
                txn.execute(
                    s.delete().where((s.c.sessionID == token) &
                                     (s.c.confidential == true()))
                ) for token in tokens
            ])
        return invalidate


    def newSession(self, isConfidential, authenticatedBy):
        # type: (bool, SessionMechanism) -> Any
        @self._dataStore.sql
        @inlineCallbacks
        def created(txn):
            # type: (Transaction) -> Any
            identifier = hexlify(urandom(32)).decode('ascii')
            s = sessionSchema.session
            yield txn.execute(s.insert().values(
                sessionID=identifier,
                confidential=isConfidential,
            ))
            returnValue(SQLSession(self,
                                   identifier=identifier,
                                   isConfidential=isConfidential,
                                   authenticatedBy=authenticatedBy))
        return created


    def loadSession(self, identifier, isConfidential, authenticatedBy):
        # type: (Text, bool, SessionMechanism) -> Any
        @self._dataStore.sql
        @inlineCallbacks
        def loaded(engine):
            # type: (Transaction) -> Any
            s = sessionSchema.session
            result = yield engine.execute(
                s.select((s.c.sessionID == identifier) &
                         (s.c.confidential == isConfidential)))
            results = yield result.fetchall()
            if not results:
                raise NoSuchSession()
            fetched_identifier = results[0][s.c.sessionID]
            returnValue(SQLSession(self,
                                   identifier=fetched_identifier,
                                   isConfidential=isConfidential,
                                   authenticatedBy=authenticatedBy))
        return loaded



@implementer(ISimpleAccountBinding)
@attr.s
class AccountSessionBinding(object):
    """
    (Stateless) binding between an account and a session, so that sessions can
    attach to, detach from, .
    """

    _plugin = attr.ib(type='AccountBindingStorePlugin')
    _session = attr.ib(type=ISession)
    _dataStore = attr.ib(type=DataStore)

    def _account(self, accountID, username, email):
        # type: (Text, Text, Text) -> SQLAccount
        """
        Construct an L{SQLAccount} bound to this plugin & dataStore.
        """
        return SQLAccount(self._plugin, self._dataStore, accountID, username,
                          email)


    @inlineCallbacks
    def createAccount(self, username, email, password):
        # type: (Text, Text, Text) -> Any
        """
        Create a new account with the given username, email and password.

        @return: an L{Account} if one could be created, L{None} if one could
            not be.
        """
        computedHash = yield computeKeyText(password)

        @self._dataStore.sql
        @inlineCallbacks
        def store(engine):
            # type: (Transaction) -> Any
            newAccountID = unicode(uuid4())
            insert = (sessionSchema.account.insert()
                      .values(accountID=newAccountID,
                              username=username, email=email,
                              passwordBlob=computedHash))
            try:
                yield engine.execute(insert)
            except IntegrityError:
                returnValue(None)
            else:
                returnValue(newAccountID)
        accountID = (yield store)
        if accountID is None:
            returnValue(None)
        account = self._account(accountID, username, email)
        returnValue(account)


    @inlineCallbacks
    def log_in(self, username, password):
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

        @self._dataStore.sql
        @inlineCallbacks
        def retrieve(engine):
            # type: (Transaction) -> Any
            result = yield engine.execute(
                acc.select(acc.c.username == username)
            )
            returnValue((yield result.fetchall()))
        accountsInfo = yield retrieve
        if not accountsInfo:
            # no account, bye
            returnValue(None)
        [row] = accountsInfo
        stored_password_text = row[acc.c.passwordBlob]
        accountID = row[acc.c.accountID]

        def reset_password(newPWText):
            # type: (Text) -> Any
            @self._dataStore.sql
            def storenew(engine):
                # type: (Transaction) -> Any
                a = sessionSchema.account
                return engine.execute(
                    a.update(a.c.accountID == accountID)
                    .values(passwordBlob=newPWText)
                )
            return storenew

        if (yield checkAndReset(stored_password_text,
                                password,
                                reset_password)):
            account = self._account(accountID, row[acc.c.username],
                                    row[acc.c.email])
            yield account.add_session(self._session)
            returnValue(account)


    def authenticated_accounts(self):
        # type: () -> Any
        """
        Retrieve the accounts currently associated with this session.

        @return: L{Deferred} firing with a L{list} of accounts.
        """
        @self._dataStore.sql
        @inlineCallbacks
        def retrieve(engine):
            # type: (Transaction) -> Any
            ast = sessionSchema.sessionAccount
            acc = sessionSchema.account
            result = (yield (yield engine.execute(
                ast.join(acc, ast.c.accountID == acc.c.accountID)
                .select(ast.c.sessionID == self._session.identifier,
                        use_labels=True)
            )).fetchall())
            returnValue([
                self._account(it[ast.c.accountID], it[acc.c.username],
                              it[acc.c.email])
                for it in result
            ])
        return retrieve


    def attached_sessions(self):
        # type: () -> Any
        """
        Retrieve information about all sessions attached to the same account
        that this session is.

        @return: L{Deferred} firing a L{list} of L{SessionIPInformation}
        """
        acs = sessionSchema.sessionAccount
        # XXX FIXME this is a bad way to access the table, since the table
        # is not actually part of the interface passed here
        sipt = (next(iter(self._dataStore.componentsProviding(
            implementedBy(IPTrackingProcurer)
        )))._session_ip_table)

        @self._dataStore.sql
        @inlineCallbacks
        def query(conn):
            # type: (Transaction) -> Any
            acs2 = acs.alias()
            from sqlalchemy.sql.expression import select
            result = yield conn.execute(
                select([sipt], use_labels=True)
                .where(
                    (acs.c.sessionID == self._session.identifier) &
                    (acs.c.accountID == acs2.c.accountID) &
                    (acs2.c.sessionID == sipt.c.sessionID)
                )
            )
            returnValue([
                SessionIPInformation(
                    id=row[sipt.c.sessionID],
                    ip=row[sipt.c.ip_address],
                    when=row[sipt.c.last_used])
                for row in (yield result.fetchall())
            ])
        return query


    def log_out(self):
        # type: () -> Any
        """
        Disassociate this session from any accounts it's logged in to.

        @return: a L{Deferred} that fires when the account is logged out.
        """
        @self._dataStore.sql
        def retrieve(engine):
            # type: (Transaction) -> Deferred
            ast = sessionSchema.sessionAccount
            return engine.execute(ast.delete(
                ast.c.sessionID == self._session.identifier
            ))
        return retrieve




@implementer(ISimpleAccount)
@attr.s
class SQLAccount(object):
    """
    An implementation of L{ISimpleAccount} backed by an Alchimia data store.
    """

    _plugin = attr.ib(type='AccountBindingStorePlugin')
    _dataStore = attr.ib(type=DataStore)
    accountID = attr.ib(type=Text)
    username = attr.ib(type=Text)
    email = attr.ib(type=Text)


    def add_session(self, session):
        # type: (ISession) -> Deferred
        """
        Add a session to the database.
        """
        @self._dataStore.sql
        def createrow(engine):
            # type: (Transaction) -> Deferred
            return engine.execute(
                sessionSchema.sessionAccount
                .insert().values(accountID=self.accountID,
                                 sessionID=session.identifier)
            )
        return createrow


    @inlineCallbacks
    def change_password(self, new_password):
        # type: (Text) -> Any
        """
        @param new_password: The text of the new password.
        @type new_password: L{unicode}
        """
        computed_hash = yield computeKeyText(new_password)

        @self._dataStore.sql
        def change(engine):
            # type: (Transaction) -> Deferred
            return engine.execute(
                sessionSchema.account.update()
                .where(accountID=self.accountID)
                .values(passwordBlob=computed_hash)
            )
        returnValue((yield change))



@implementer(ISQLAuthorizer)
@attr.s()
class AccountBindingStorePlugin(object):
    """
    An authorizer for L{ISimpleAccountBinding} based on an alchimia dataStore.
    """

    _dataStore = attr.ib(type=DataStore)

    authzn_for = ISimpleAccountBinding

    def authzn_for_session(
            self,
            sessionStore,      # type: AlchimiaSessionStore
            transaction,        # type: Transaction
            session             # type: ISession
    ):
        # type: (...) -> AccountSessionBinding
        return AccountSessionBinding(self, session, self._dataStore)


@implementer(ISQLAuthorizer)
@attr.s()
class AccountLoginAuthorizer(object):
    """
    An authorizor for an L{ISimpleAccount} based on an alchimia data store.
    """

    authzn_for = ISimpleAccount

    _dataStore = attr.ib(type=DataStore)

    @inlineCallbacks
    def authzn_for_session(self, sessionStore, transaction, session):
        # type: (AlchimiaSessionStore, Transaction, SQLSession) -> Any
        """
        Authorize a given session for having a simple account logged in to it,
        returning None if that session is not bound to an account.
        """
        binding = (yield session.authorize([ISimpleAccountBinding])
                   )[ISimpleAccountBinding]
        returnValue(next(iter((yield binding.authenticated_accounts())),
                         None))



@inlineCallbacks
def upsert(
        engine,                 # type: Transaction
        table,                  # type: sqlalchemy.schema.Table
        to_query,               # type: Dict[str, Any]
        to_change               # type: Dict[str, Any]
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
        update = table.update().where(
            reduce(And, (
                (getattr(table.c, cname) == cvalue)
                for (cname, cvalue) in to_query.items()
            ))
        ).values(**to_change)
        result = yield engine.execute(update)
    returnValue(result)


@attr.s
class SessionSchema(object):
    """
    Schema for SQL session features.
    """

    session = attr.ib(type=Table)
    account = attr.ib(type=Table)
    sessionAccount = attr.ib(type=Table)
    sessionIP = attr.ib(type=Table)

    @classmethod
    def withMetadata(cls, metadata: MetaData) -> 'SessionSchema':
        """
        Create a new L{SQLSessionSchema} with the given metadata.
        """
        session = Table(
            "session", metadata,
            Column("session_id", Unicode(), primary_key=True,
                   nullable=False),
            Column("confidential", Boolean(), nullable=False),
        )
        account = Table(
            "account", metadata,
            Column("account_id", Unicode(), primary_key=True,
                   nullable=False),
            Column("username", Unicode(), unique=True, nullable=False),
            Column("email", Unicode(), nullable=False),
            Column("password_blob", Unicode(), nullable=False),
        )
        sessionAccount = Table(
            "session_account", metadata,
            Column("account_id", Unicode(),
                   ForeignKey(account.c.account_id, ondelete="CASCADE")),
            Column("session_id", Unicode(),
                   ForeignKey(session.c.session_id, ondelete="CASCADE")),
            UniqueConstraint("account_id", "session_id"),
        )
        sessionIP = Table(
            "session_ip", metadata,
            Column("session_id", Unicode(),
                   ForeignKey(session.c.session_id, ondelete="CASCADE")),
            Column("ip_address", Unicode(), nullable=False),
            Column("address_family", Unicode(), nullable=False),
            Column("last_used", DateTime(), nullable=False),
            UniqueConstraint("session_id", "ip_address", "address_family"),
        )
        return cls(session, account, sessionAccount, sessionIP)

sessionSchema = SessionSchema.withMetadata(MetaData())

@implementer(ISessionProcurer)
class IPTrackingProcurer(object):
    """
    An implementation of L{ISessionProcurer} that keeps track of the source IP
    of the originating session.
    """

    def __init__(
            self,
            dataStore,          # type: DataStore
            procurer            # type: ISessionProcurer
    ):
        # type: (...) -> None
        """
        Create an L{IPTrackingProcurer} from SQLAlchemy metadata, an alchimia
        data store, and an existing L{ISessionProcurer}.
        """
        self._dataStore = dataStore
        self._procurer = procurer


    def procureSession(self, request, forceInsecure=False,
                       alwaysCreate=True):
        # type: (IRequest, bool, bool) -> Deferred
        """
        Procure a session from the underlying procurer, keeping track of the IP
        of the request object.
        """
        andThen = (self._procurer
                   .procureSession(request, forceInsecure, alwaysCreate)
                   .addCallback)

        @andThen
        def _(session):
            # type: (SQLSession) -> Any
            if session is None:
                return
            sessionID = session.identifier
            try:
                ip_address = (request.client.host or b"").decode("ascii")
            except BaseException:
                ip_address = u""

            @self._dataStore.sql
            def touch(engine):
                # type: (Transaction) -> Deferred
                address_family = (u"AF_INET6" if u":" in ip_address
                                  else u"AF_INET")
                last_used = datetime.utcnow()
                sip = sessionSchema.sessionIP
                return upsert(engine, sip,
                              dict(sessionID=sessionID,
                                   ip_address=ip_address,
                                   address_family=address_family),
                              dict(last_used=last_used))

            @touch.addCallback
            def andReturn(ignored):
                # type: (Any) -> SQLSession
                return session
            return andReturn

        @_.addCallback
        def showMe(result):
            # type: (T) -> T
            return result
        return _


procurerFromStoreT = Callable[[ISessionStore], ISessionProcurer]

def openSessionStore(
        reactor,                # type: IReactorThreads
        databaseURL,            # type: Text
        componentCreators=(),   # type: Iterable[Callable]
        procurerFromStore=SessionProcurer  # type: procurerFromStoreT
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
    dataStore = DataStore.open(
        reactor, databaseURL, [
            lambda dataStore: AlchimiaSessionStore(dataStore),
            AccountBindingStorePlugin,
            lambda dataStore:
            IPTrackingProcurer(
                dataStore, procurerFromStore(
                    next(iter(dataStore.componentsProviding(ISessionStore))))),
            AccountLoginAuthorizer,
        ] + list(componentCreators)
    )
    return next(iter(dataStore.componentsProviding(ISessionProcurer)))



class _FunctionWithAuthorizer(object):

    authorizer = None           # type: Any

    def __call__(
            self,
            metadata,           # type: MetaData
            dataStore,          # type: DataStore
            sessionStore,       # type: AlchimiaSessionStore
            transaction,        # type: Transaction
            session             # type: ISession
    ):
        # type: (...) -> Any
        """
        Signature for a function that can have an authorizer attached to it.
        """

_authorizerFunction = Callable[
    [DataStore, AlchimiaSessionStore, Transaction, ISession],
    Any
]

@implementer(ISQLAuthorizer)
@attr.s
class AnAuthorizer(object):
    dataStore = attr.ib(type=DataStore)
    authzn_for = attr.ib(type=Type)
    _decorated = attr.ib(type=_authorizerFunction)

    def authzn_for_session(self, sessionStore, transaction, session):
        # type: (AlchimiaSessionStore, Transaction, ISession) -> Any
        cb = cast(_authorizerFunction, self._decorated)  # type: ignore
        return cb(self.dataStore, sessionStore, transaction, session)

def authorizerFor(
        authzn_for,                        # type: Type
):
    # type: (...) -> Callable[[Callable], _FunctionWithAuthorizer]
    """
    Declare an SQL authorizer, implemented by a given function.  Used like so::

        @authorizerFor(Foo, tables(foo=[Column("bar", Unicode())]))
        def authorizeFoo(dataStore, sessionStore, transaction, session):
            return Foo(metadata, metadata.tables["foo"])

    @param authzn_for: The type we are creating an authorizer for.

    @return: a decorator that can decorate a function with the signature
        C{(metadata, dataStore, sessionStore, transaction, session)}
    """
    def decorator(decorated):
        # type: (_authorizerFunction) -> _FunctionWithAuthorizer
        result = cast(_FunctionWithAuthorizer, decorated)

        def curriedAuthorizer(dataStore):
            # type: (DataStore) -> ISQLAuthorizer
            return cast(ISQLAuthorizer,
                        AnAuthorizer(dataStore, authzn_for, decorated))
        result.authorizer = curriedAuthorizer
        return result
    return decorator
