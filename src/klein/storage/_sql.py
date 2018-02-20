
from binascii import hexlify
from collections import deque
from datetime import datetime
from functools import reduce
from os import urandom
from uuid import uuid4

from typing import Any, Callable, Type, TypeVar, TYPE_CHECKING, Iterable, Text, List, Dict
if TYPE_CHECKING:
    import sqlalchemy
    from twisted.internet.defer import Deferred
    from twisted.internet.interfaces import IReactorThreads
    from twisted.web.iweb import IRequest
    from .._interfaces import SessionMechanism
    Any, Callable, Deferred, Type, Iterable, IReactorThreads, Text, List, sqlalchemy, SessionMechanism, Dict, IRequest
    I = TypeVar('I')

from alchimia import TWISTED_STRATEGY

import attr
from attr import Factory
from attr.validators import instance_of as an

from six import text_type

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, MetaData, Table, Unicode,
    UniqueConstraint, create_engine, true
)
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.schema import CreateTable

from twisted.internet.defer import (
    gatherResults, inlineCallbacks, maybeDeferred, returnValue
)
from twisted.python.compat import unicode
from twisted.python.failure import Failure

from zope.interface import implementedBy, implementer, IInterface

from ._security import checkAndReset, computeKeyText
from .. import SessionProcurer
from klein._zitype import zcast
from ..interfaces import (
    ISQLAuthorizer, ISQLSchemaComponent, ISession,
    ISessionProcurer, ISessionStore, ISimpleAccount, ISimpleAccountBinding,
    NoSuchSession, TransactionEnded
)

@implementer(ISession)
@attr.s
class SQLSession(object):
    _sessionStore = attr.ib()
    identifier = attr.ib()
    isConfidential = attr.ib()
    authenticatedBy = attr.ib()

    if TYPE_CHECKING:
        def __init__(self, sessionStore, identifier, isConfidential, authenticatedBy):
            # type: (AlchimiaSessionStore, Text, bool, SessionMechanism) -> None
            pass

    def authorize(self, interfaces):
        # type: (Iterable[IInterface]) -> Any
        interfaces = set(interfaces)
        datastore = self._sessionStore._datastore

        @datastore.sql
        def authzn(txn):
            # type: (Transaction) -> Deferred
            result = {}
            ds = []
            authorizers = datastore.componentsProviding(ISQLAuthorizer)
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
                # type: (I) -> Dict[str, Any]
                return result
            return (gatherResults(ds).addCallback(r))
        return authzn



@attr.s
class SessionIPInformation(object):
    """
    Information about a session being used from a given IP address.
    """
    id = attr.ib(validator=an(text_type))
    ip = attr.ib(validator=an(text_type))
    when = attr.ib(validator=an(datetime))

    if TYPE_CHECKING:
        def __init__(self, id, ip, when):
            # type: (Text, Text, datetime) -> None
            pass



@attr.s
class Transaction(object):
    """
    Wrapper around a SQLAlchemy connection which is invalidated when the
    transaction is committed or rolled back.
    """
    _connection = attr.ib()
    _stopped = attr.ib(default=False)
    if TYPE_CHECKING:
        def __init__(self, connection):
            # type: (Any) -> None
            pass

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
class AlchimiaDataStore(object):
    """
    L{AlchimiaDataStore} is a generic storage object that connect to an SQL
    database, run transactions, and manage schema metadata.
    """

    _engine = attr.ib()
    _components = attr.ib()
    _free_connections = attr.ib(default=Factory(deque))

    if TYPE_CHECKING:
        def __init__(self, engine, components):
            # type: (sqlalchemy.engine.Engine, List[Any]) -> None
            pass

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
            cxn = (self._free_connections.popleft() if self._free_connections
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
            self._free_connections.append(cxn)


    def componentsProviding(self, interface):
        # type: (Type[I]) -> Iterable[I]
        """
        Get all the components providing the given interface.
        """
        for component in self._components:
            if zcast(IInterface, interface).providedBy(component):
                # Adaptation-by-call doesn't work with implementedBy() objects
                # so we can't query for classes
                yield component


    @classmethod
    def open(cls, reactor, dbURL, componentCreators):
        # type: (IReactorThreads, Text, Iterable[Callable]) -> Deferred
        """
        Open an L{AlchimiaDataStore}.

        @param reactor: the reactor that this store should be opened on.
        @type reactor: L{IReactorThreads}

        @param dbURL: the SQLAlchemy database URI to connect to.
        @type dbURL: L{str}

        @param componentCreators: callables which can create components.
        @type componentCreators: C{iterable} of L{callable} taking 2
            arguments; (L{MetaData}, L{AlchimiaDataStore}), and returning a
            non-C{None} value.
        """
        metadata = MetaData()
        components = []         # type: List[Any]
        self = cls(
            create_engine(dbURL, reactor=reactor, strategy=TWISTED_STRATEGY),
            components,
        )
        components.extend(creator(metadata, self)
                          for creator in componentCreators)
        return self._populateSchema().addCallback(lambda ignored: self)


    def _populateSchema(self):
        # type: () -> Deferred
        """
        Populate the schema.
        """
        @self.sql
        @inlineCallbacks
        def do(transaction):
            # type: (Transaction) -> Any
            for component in self.componentsProviding(ISQLSchemaComponent):
                try:
                    yield component.initialize_schema(transaction)
                except OperationalError as oe:
                    # Table creation failure.  TODO: log this error.
                    print("OE:", oe)
        return do


@implementer(ISessionStore, ISQLSchemaComponent)
@attr.s(init=False)
class AlchimiaSessionStore(object):
    """
    An implementation of L{ISessionStore} based on an L{AlchimiaStore}, that
    stores sessions in a SQLAlchemy database.
    """

    def __init__(self, metadata, datastore):
        # type: (sqlalchemy.schema.MetaData, AlchimiaDataStore) -> None
        """
        Create an L{AlchimiaSessionStore} from a L{AlchimiaStore}.
        """
        self._datastore = datastore
        self.session_table = Table(
            "session", metadata,
            Column("sessionID", Unicode(), primary_key=True, nullable=False),
            Column("confidential", Boolean(), nullable=False),
        )

    def sentInsecurely(self, tokens):
        # type: (List[str]) -> Deferred
        """
        Tokens have been sent insecurely; delete any tokens expected to be
        confidential.

        @param tokens: L{list} of L{str}

        @return: a L{Deferred} that fires when the tokens have been
            invalidated.
        """
        @self._datastore.sql
        def invalidate(txn):
            # type: (Transaction) -> Deferred
            s = self.session_table
            return gatherResults([
                txn.execute(
                    s.delete().where((s.c.sessionID == token) &
                                     (s.c.confidential == true()))
                ) for token in tokens
            ])
        return invalidate


    @inlineCallbacks
    def initialize_schema(self, transaction):
        # type: (Transaction) -> Any
        """
        Initialize session-specific schema.
        """
        try:
            yield transaction.execute(CreateTable(self.session_table))
        except OperationalError as oe:
            print("sessions-table", oe)


    def newSession(self, isConfidential, authenticatedBy):
        # type: (bool, SessionMechanism) -> Any
        @self._datastore.sql
        @inlineCallbacks
        def created(txn):
            # type: (Transaction) -> Any
            identifier = hexlify(urandom(32)).decode('ascii')
            s = self.session_table
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
        @self._datastore.sql
        @inlineCallbacks
        def loaded(engine):
            # type: (Transaction) -> Any
            s = self.session_table
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
    _plugin = attr.ib()
    _session = attr.ib()
    _datastore = attr.ib()

    if TYPE_CHECKING:
        def __init__(self, plugin, session, datastore):
            # type: (AccountBindingStorePlugin, ISession, AlchimiaDataStore) -> None
            pass

    def _account(self, accountID, username, email):
        # type: (Text, Text, Text) -> SQLAccount
        """
        Construct an L{SQLAccount} bound to this plugin & datastore.
        """
        return SQLAccount(self._plugin, self._datastore, accountID, username,
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

        @self._datastore.sql
        @inlineCallbacks
        def store(engine):
            # type: (Transaction) -> Any
            newAccountID = unicode(uuid4())
            insert = (self._plugin.accountTable.insert()
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
        acc = self._plugin.accountTable

        @self._datastore.sql
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
            @self._datastore.sql
            def storenew(engine):
                # type: (Transaction) -> Any
                a = self._plugin.accountTable
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
        @self._datastore.sql
        @inlineCallbacks
        def retrieve(engine):
            # type: (Transaction) -> Any
            ast = self._plugin.account_session_table
            acc = self._plugin.accountTable
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
        acs = self._plugin.account_session_table
        # XXX FIXME this is a bad way to access the table, since the table
        # is not actually part of the interface passed here
        sipt = (next(self._datastore.componentsProviding(
            implementedBy(IPTrackingProcurer)
        ))._session_ip_table)

        @self._datastore.sql
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
        @self._datastore.sql
        def retrieve(engine):
            # type: (Transaction) -> Deferred
            ast = self._plugin.account_session_table
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

    _plugin = attr.ib()
    _datastore = attr.ib()
    accountID = attr.ib()
    username = attr.ib()
    email = attr.ib()

    if TYPE_CHECKING:
        def __init__(self, plugin, datastore, accountID, username, email):
            # type: (ISQLSchemaComponent, AlchimiaDataStore, Text, Text, Text) -> None
            pass

    def add_session(self, session):
        # type: (ISession) -> Deferred
        """
        Add a session to the database.
        """
        @self._datastore.sql
        def createrow(engine):
            # type: (Transaction) -> Deferred
            return engine.execute(
                self._plugin.account_session_table
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

        @self._datastore.sql
        def change(engine):
            # type: (Transaction) -> Deferred
            return engine.execute(
                self._plugin.accountTable.update()
                .where(accountID=self.accountID)
                .values(passwordBlob=computed_hash)
            )
        returnValue((yield change))



@implementer(ISQLAuthorizer, ISQLSchemaComponent)
class AccountBindingStorePlugin(object):
    """
    An authorizer for L{ISimpleAccountBinding} based on an alchimia datastore.
    """

    authzn_for = ISimpleAccountBinding

    def __init__(self, metadata, store):
        # type: (sqlalchemy.schema.MetaData, AlchimiaDataStore) -> None
        """
        Create an account binding authorizor from some SQLAlchemy metadata and
        an L{AlchimiaDataStore}.
        """
        self._datastore = store

        self.accountTable = Table(
            "account", metadata,
            Column("accountID", Unicode(), primary_key=True,
                   nullable=False),
            Column("username", Unicode(), unique=True, nullable=False),
            Column("email", Unicode(), nullable=False),
            Column("passwordBlob", Unicode(), nullable=False),
        )

        self.account_session_table = Table(
            "account_session", metadata,
            Column("accountID", Unicode(),
                   ForeignKey("account.accountID", ondelete="CASCADE")),
            Column("sessionID", Unicode(),
                   ForeignKey("session.sessionID", ondelete="CASCADE")),
            UniqueConstraint("accountID", "sessionID"),
        )


    @inlineCallbacks
    def initialize_schema(self, transaction):
        # type: (Transaction) -> Any
        """
        Initialize this plugin's schema.
        """
        for table in [self.accountTable, self.account_session_table]:
            yield transaction.execute(CreateTable(table))


    def authzn_for_session(self, session_store, transaction, session):
        # type: (AlchimiaSessionStore, Transaction, ISession) -> AccountSessionBinding
        return AccountSessionBinding(self, session, self._datastore)


@implementer(ISQLAuthorizer)
class AccountLoginAuthorizer(object):
    """
    An authorizor for an L{ISimpleAccount} based on an alchimia data store.
    """

    authzn_for = ISimpleAccount

    def __init__(self, metadata, store):
        # type: (sqlalchemy.schema.MetaData, AlchimiaDataStore) -> None
        """
        Create an L{AccountLoginAuthorizer} from SQLAlchemy metadata and an
        alchimia data store.
        """
        self.datastore = store

    @inlineCallbacks
    def authzn_for_session(self, session_store, transaction, session):
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
def upsert(engine, table, to_query, to_change):
    # type: (Transaction, sqlalchemy.schema.Table, Dict[str, Any], Dict[str, Any]) -> Any
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



@implementer(ISessionProcurer, ISQLSchemaComponent)
class IPTrackingProcurer(object):
    """
    An implementatino of L{ISessionProcurer} that keeps track of the source IP
    of the originating session.
    """

    def __init__(self, metadata, datastore, procurer):
        # type: (sqlalchemy.schema.MetaData, AlchimiaDataStore, ISessionProcurer) -> None
        """
        Create an L{IPTrackingProcurer} from SQLAlchemy metadata, an alchimia
        data store, and an existing L{ISessionProcurer}.
        """
        self._session_ip_table = Table(
            "session_ip", metadata,
            Column("sessionID", Unicode(),
                   ForeignKey("session.sessionID", ondelete="CASCADE"),
                   nullable=False),
            Column("ip_address", Unicode(), nullable=False),
            Column("address_family", Unicode(), nullable=False),
            Column("last_used", DateTime(), nullable=False),
            UniqueConstraint("sessionID", "ip_address", "address_family"),
        )
        self._datastore = datastore
        self._procurer = procurer


    @inlineCallbacks
    def initialize_schema(self, transaction):
        # type: (Transaction) -> Any
        """
        Create the requisite table for storing IP addresses for this
        L{IPTrackingProcurer}.
        """
        try:
            yield transaction.execute(CreateTable(self._session_ip_table))
        except OperationalError as oe:
            print("ip-schema", oe)


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

            @self._datastore.sql
            def touch(engine):
                # type: (Transaction) -> Deferred
                address_family = (u"AF_INET6" if u":" in ip_address
                                  else u"AF_INET")
                last_used = datetime.utcnow()
                sip = self._session_ip_table
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
            # type: (I) -> I
            return result
        return _



def openSessionStore(reactor, db_uri, component_creators=(),
                     procurer_from_store=SessionProcurer):
    # type: (IReactorThreads, Text, Iterable[Callable], Callable) -> Deferred
    """
    Open a session store, returning a procurer that can procure sessions from
    it.

    @param db_uri: an SQLAlchemy database URI.
    @type db_uri: L{str}

    @param procurer_from_store: A callable that takes an L{ISessionStore} and
        returns an L{ISessionProcurer}.
    @type procurer_from_store: L{callable}

    @return: L{Deferred} firing with L{ISessionProcurer}
    """
    opened = AlchimiaDataStore.open(
        reactor, db_uri, [
            lambda metadata, store: AlchimiaSessionStore(metadata, store),
            AccountBindingStorePlugin,
            lambda metadata, store:
            IPTrackingProcurer(
                metadata, store, procurer_from_store(
                    next(iter(
                        store.componentsProviding(
                            ISessionStore)
                )))),
            AccountLoginAuthorizer,
        ] + list(component_creators)
    ).addCallback

    @opened
    def procurify(datastore):
        # type: (AlchimiaDataStore) -> ISessionProcurer
        return next(iter(datastore.componentsProviding(ISessionProcurer)))
    return procurify



def tables(**kw):
    # type: (**Any) -> Any
    """
    Take a mapping of table names to columns and return a callable that takes a
    transaction and metadata and then ensures those tables with those columns
    exist.

    This is a quick-start way to initialize your schema; any kind of
    application that has a longer maintenance cycle will need a more
    sophisticated schema-migration approach.
    """
    @inlineCallbacks
    def callme(transaction, metadata):
        # type: (Transaction, sqlalchemy.schema.MetaData) -> Any
        # TODO: inspect information schema, verify tables exist, don't try to
        # create them otherwise.
        for k, v in kw.items():
            print("creating table", k)
            try:
                yield transaction.execute(
                    CreateTable(Table(k, metadata, *v))
                )
            except OperationalError as oe:
                print("failure initializing table", k, oe)
    return callme



def authorizerFor(authzn_for, schema=lambda txn, metadata: None):
    # type: (Type, Callable[[Transaction, sqlalchemy.schema.MetaData], Deferred]) -> Callable[[Callable], Any]
    """
    Declare an SQL authorizer, implemented by a given function.  Used like so::

        @authorizerFor(Foo, tables(foo=[Column("bar", Unicode())]))
        def authorize_foo(metadata, datastore, session_store, transaction,
                          session):
            return Foo(metadata, metadata.tables["foo"])

    @param authzn_for: The type we are creating an authorizer for.

    @param schema: a callable that takes a transaction and metadata, and
        returns a L{Deferred} which fires when it's done initializing the
        schema on that transaction.  See L{tables} for a convenient way to
        specify that.

    @return: a decorator that can decorate a function with the signature
        C{(metadata, datastore, session_store, transaction, session)}
    """
    an_authzn = authzn_for

    def decorator(decorated):
        # type: (Callable) -> Callable
        @implementer(ISQLAuthorizer, ISQLSchemaComponent)
        @attr.s
        class AnAuthorizer(object):
            metadata = attr.ib()
            datastore = attr.ib()

            authzn_for = an_authzn

            def initialize_schema(self, transaction):
                # type: (Transaction) -> Any
                return schema(transaction, self.metadata)

            def authzn_for_session(self, session_store, transaction, session):
                # type: (AlchimiaSessionStore, Transaction, ISession) -> Any
                return decorated(self.metadata, self.datastore, session_store,
                                 transaction, session)

        decorated.authorizer = AnAuthorizer
        return decorated
    return decorator
