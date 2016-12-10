
from datetime import datetime
from six import text_type
from collections import deque

from binascii import hexlify
from os import urandom
from uuid import uuid4

from zope.interface import implementer, provider, implementedBy

from attr import Factory
from attr.validators import instance_of as an

import attr
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Boolean, String,
    ForeignKey, DateTime, UniqueConstraint
)
from sqlalchemy.schema import CreateTable
from sqlalchemy.exc import OperationalError, IntegrityError
from alchimia import TWISTED_STRATEGY

from ..interfaces import (
    ISession, ISessionStore, NoSuchSession, ISimpleAccount,
    ISimpleAccountBinding, ISessionProcurer, ISQLSchemaComponent,
    TransactionEnded, ISQLAuthorizer
)

from .. import SessionProcurer

from twisted.internet.defer import (
    inlineCallbacks, returnValue, gatherResults, maybeDeferred
)
from twisted.python.failure import Failure

from .security import compute_key_text, check_and_reset

@implementer(ISession)
@attr.s
class SQLSession(object):
    _session_store = attr.ib()
    identifier = attr.ib()
    is_confidential = attr.ib()
    authenticated_by = attr.ib()

    def authorize(self, interfaces):
        interfaces = set(interfaces)
        datastore = self._session_store._datastore
        @datastore.sql
        def authzn(txn):
            result = {}
            ds = []
            authorizers = datastore.components_providing(ISQLAuthorizer)
            for a in authorizers:
                # This should probably do something smart with interface
                # priority, checking isOrExtends or something similar.
                if a.authzn_for in interfaces:
                    v = maybeDeferred(a.authzn_for_session,
                                      self._session_store, txn, self)
                    ds.append(v)
                    result[a.authzn_for] = v
                    v.addCallback(
                        lambda value, ai: result.__setitem__(ai, value),
                        ai=a.authzn_for
                    )
            def r(ignored):
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



@attr.s
class Transaction(object):
    """
    Wrapper around a SQLAlchemy connection which is invalidated when the
    transaction is committed or rolled back.
    """
    _connection = attr.ib()
    _stopped = attr.ib(default=False)

    def execute(self, statement, *multiparams, **params):
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

    @inlineCallbacks
    def sql(self, callable):
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
            except:
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


    def components_providing(self, interface):
        """
        Get all the components providing the given interface.
        """
        for component in self._components:
            if interface.providedBy(component):
                # Adaptation-by-call doesn't work with implementedBy() objects
                # so we can't query for classes
                yield component


    @classmethod
    def open(cls, reactor, db_url, component_creators):
        """
        Open an L{AlchimiaDataStore}.

        @param reactor: the reactor that this store should be opened on.
        @type reactor: L{IReactorThreads}

        @param db_url: the SQLAlchemy database URI to connect to.
        @type db_url: L{str}

        @param component_creators: callables which can create components.
        @type component_creators: C{iterable} of L{callable} taking 2
            arguments; (L{MetaData}, L{AlchimiaDataStore}), and returning a
            non-C{None} value.
        """
        metadata = MetaData()
        components = []
        self = cls(
            create_engine(db_url, reactor=reactor, strategy=TWISTED_STRATEGY),
            components,
        )
        components.extend(creator(metadata, self)
                          for creator in component_creators)
        return self._populate_schema().addCallback(lambda ignored: self)


    def _populate_schema(self):
        """
        Populate the schema.
        """
        @self.sql
        @inlineCallbacks
        def do(transaction):
            for component in self.components_providing(ISQLSchemaComponent):
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
    
    """

    def __init__(self, metadata, datastore):
        """
        Create an L{AlchimiaSessionStore} from a L{AlchimiaStore}.
        """
        self._datastore = datastore
        self.session_table = Table(
            "session", metadata,
            Column("session_id", String(), primary_key=True, nullable=False),
            Column("confidential", Boolean(), nullable=False),
        )

    def sent_insecurely(self, tokens):
        """
        Tokens have been sent insecurely; delete any tokens expected to be
        confidential.

        @param tokens: L{list} of L{str}

        @return: a L{Deferred} that fires when the tokens have been
            invalidated.
        """
        @self._datastore.sql
        def invalidate(txn):
            s = self.session_table
            return gatherResults([
                txn.execute(
                    s.delete().where((s.c.session_id == token) &
                                     (s.c.confidential == True))
                ) for token in tokens
            ])
        return invalidate


    @inlineCallbacks
    def initialize_schema(self, transaction):
        """
        Initialize session-specific schema.
        """
        try:
            yield transaction.execute(CreateTable(self.session_table))
        except OperationalError as oe:
            print("sessions-table", oe)


    def new_session(self, is_confidential, authenticated_by):
        @self._datastore.sql
        @inlineCallbacks
        def created(txn):
            identifier = hexlify(urandom(32))
            s = self.session_table
            yield txn.execute(s.insert().values(
                session_id=identifier,
                confidential=is_confidential,
            ))
            returnValue(SQLSession(self,
                                   identifier=identifier,
                                   is_confidential=is_confidential,
                                   authenticated_by=authenticated_by))
        return created


    def load_session(self, identifier, is_confidential, authenticated_by):
        @self._datastore.sql
        @inlineCallbacks
        def loaded(engine):
            s = self.session_table
            result = yield engine.execute(
                s.select((s.c.session_id==identifier) &
                         (s.c.confidential==is_confidential)))
            results = yield result.fetchall()
            if not results:
                raise NoSuchSession()
            fetched_identifier = results[0][s.c.session_id]
            returnValue(SQLSession(self,
                                   identifier=fetched_identifier,
                                   is_confidential=is_confidential,
                                   authenticated_by=authenticated_by))
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

    def _account(self, account_id, username, email):
        """
        
        """
        return SQLAccount(self._plugin, self._datastore, account_id, username,
                          email)


    @inlineCallbacks
    def create_account(self, username, email, password):
        """
        Create a new account with the given username, email and password.

        @return: an L{Account} if one could be created, L{None} if one could
            not be.
        """
        computedHash = yield compute_key_text(password)
        @self._datastore.sql
        @inlineCallbacks
        def store(engine):
            new_account_id = unicode(uuid4())
            insert = (self._plugin.account_table.insert()
                      .values(account_id=new_account_id,
                              username=username, email=email,
                              password_blob=computedHash))
            try:
                yield engine.execute(insert)
            except IntegrityError:
                returnValue(None)
            else:
                returnValue(new_account_id)
        account_id = (yield store)
        if account_id is None:
            returnValue(None)
        account = self._account(account_id, username, email)
        returnValue(account)


    @inlineCallbacks
    def log_in(self, username, password):
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
        acc = self._plugin.account_table
        @self._datastore.sql
        @inlineCallbacks
        def retrieve(engine):
            result = yield engine.execute(
                acc.select(acc.c.username == username)
            )
            returnValue((yield result.fetchall()))
        accounts_info = yield retrieve
        if not accounts_info:
            # no account, bye
            returnValue(None)
        [row] = accounts_info
        stored_password_text = row[acc.c.password_blob]
        account_id = row[acc.c.account_id]

        def reset_password(new_pw_text):
            @self._datastore.sql
            def storenew(engine):
                a = self._plugin.account_table
                return engine.execute(
                    a.update(a.c.account_id == account_id)
                    .values(password_blob=new_pw_text)
                )
            return storenew

        if (yield check_and_reset(stored_password_text,
                                  password,
                                  reset_password)):
            account = self._account(account_id, row[acc.c.username],
                                    row[acc.c.email])
            yield account.add_session(self._session)
            returnValue(account)


    def authenticated_accounts(self):
        """
        Retrieve the accounts currently associated with this session.

        @return: L{Deferred} firing with a L{list} of accounts.
        """
        @self._datastore.sql
        @inlineCallbacks
        def retrieve(engine):
            ast = self._plugin.account_session_table
            acc = self._plugin.account_table
            result = (yield (yield engine.execute(
                ast.join(acc, ast.c.account_id == acc.c.account_id)
                .select(ast.c.session_id == self._session.identifier,
                        use_labels=True)
            )).fetchall())
            returnValue([
                self._account(it[ast.c.account_id], it[acc.c.username],
                              it[acc.c.email])
                for it in result
            ])
        return retrieve


    def attached_sessions(self):
        """
        Retrieve information about all sessions attached to the same account
        that this session is.

        @return: L{Deferred} firing a L{list} of L{SessionIPInformation}
        """
        acs = self._plugin.account_session_table
        # XXX FIXME this is a bad way to access the table, since the table
        # is not actually part of the interface passed here
        sipt = (next(self._datastore.components_providing(
            implementedBy(IPTrackingProcurer)
        ))._session_ip_table)
        @self._datastore.sql
        @inlineCallbacks
        def query(conn):
            acs2 = acs.alias()
            from sqlalchemy.sql.expression import select
            result = yield conn.execute(
                select([sipt], use_labels=True)
                .where((acs.c.session_id == self._session.identifier) &
                       (acs.c.account_id == acs2.c.account_id) &
                       (acs2.c.session_id == sipt.c.session_id)
                )
            )
            returnValue([
                SessionIPInformation(
                    id=row[sipt.c.session_id],
                    ip=row[sipt.c.ip_address],
                    when=row[sipt.c.last_used])
                for row in (yield result.fetchall())
            ])
        return query


    def log_out(self):
        """
        Disassociate this session from any accounts it's logged in to.

        @return: a L{Deferred} that fires when the account is logged out.
        """
        @self._datastore.sql
        def retrieve(engine):
            ast = self._plugin.account_session_table
            return engine.execute(ast.delete(
                ast.c.session_id == self._session.identifier
            ))
        return retrieve




@implementer(ISimpleAccount)
@attr.s
class SQLAccount(object):
    """
    
    """
    _plugin = attr.ib()
    _datastore = attr.ib()
    account_id = attr.ib()
    username = attr.ib()
    email = attr.ib()

    def add_session(self, session):
        """
        
        """
        @self._datastore.sql
        def createrow(engine):
            return engine.execute(
                self._plugin.account_session_table
                .insert().values(account_id=self.account_id,
                                 session_id=session.identifier)
            )
        return createrow


    @inlineCallbacks
    def change_password(self, new_password):
        """
        @param new_password: The text of the new password.
        @type new_password: L{unicode}
        """
        computed_hash = compute_key_text(new_password)
        @self._datastore.sql
        def change(engine):
            return engine.execute(
                self._plugin.account_table.update()
                .where(account_id=self.account_id)
                .values(password_blob=computed_hash)
            )
        returnValue((yield change))



@implementer(ISQLAuthorizer, ISQLSchemaComponent)
class AccountBindingStorePlugin(object):
    """
    
    """

    authzn_for = ISimpleAccountBinding

    def __init__(self, metadata, store):
        """
        
        """
        self._datastore = store

        self.account_table = Table(
            "account", metadata,
            Column("account_id", String(), primary_key=True,
                   nullable=False),
            Column("username", String(), unique=True, nullable=False),
            Column("email", String(), nullable=False),
            Column("password_blob", String(), nullable=False),
        )

        self.account_session_table = Table(
            "account_session", metadata,
            Column("account_id", String(),
                   ForeignKey("account.account_id", ondelete="CASCADE")),
            Column("session_id", String(),
                   ForeignKey("session.session_id", ondelete="CASCADE")),
            UniqueConstraint("account_id", "session_id"),
        )

    @inlineCallbacks
    def initialize_schema(self, transaction):
        """
        
        """
        for table in [self.account_table, self.account_session_table]:
            yield transaction.execute(CreateTable(table))


    def authzn_for_session(self, session_store, transaction, session):
        return AccountSessionBinding(self, session, self._datastore)


@implementer(ISQLAuthorizer)
class AccountLoginAuthorizer(object):
    """
    
    """

    authzn_for = ISimpleAccount

    def __init__(self, metadata, store):
        """
        
        """
        self.datastore = store

    @inlineCallbacks
    def authzn_for_session(self, session_store, transaction, session):
        """
        
        """
        binding = (yield session.authorize([ISimpleAccountBinding])
                   )[ISimpleAccountBinding]
        returnValue(next(iter((yield binding.authenticated_accounts())),
                         None))



@inlineCallbacks
def upsert(engine, table, to_query, to_change):
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

    def __init__(self, metadata, datastore, procurer):
        """
        
        """
        self._session_ip_table = Table(
            "session_ip", metadata,
            Column("session_id", String(),
                   ForeignKey("session.session_id", ondelete="CASCADE"),
                   nullable=False),
            Column("ip_address", String(), nullable=False),
            Column("address_family", String(), nullable=False),
            Column("last_used", DateTime(), nullable=False),
            UniqueConstraint("session_id", "ip_address", "address_family"),
        )
        self._datastore = datastore
        self._procurer = procurer


    @inlineCallbacks
    def initialize_schema(self, transaction):
        """
        
        """
        try:
            yield transaction.execute(CreateTable(self._session_ip_table))
        except OperationalError as oe:
            print("ip-schema", oe)


    def procure_session(self, request, force_insecure=False,
                        always_create=True):
        andThen = (self._procurer
                   .procure_session(request, force_insecure, always_create)
                   .addCallback)
        @andThen
        def _(session):
            if session is None:
                return
            session_id = session.identifier
            try:
                ip_address = (request.client.host or b"").decode("ascii")
            except:
                ip_address = u""
            @self._datastore.sql
            def touch(engine):
                address_family = (u"AF_INET6" if u":" in ip_address
                                  else u"AF_INET")
                last_used = datetime.utcnow()
                sip = self._session_ip_table
                return upsert(engine, sip,
                              dict(session_id=session_id,
                                   ip_address=ip_address,
                                   address_family=address_family),
                              dict(last_used=last_used))
            @touch.addCallback
            def andReturn(ignored):
                return session
            return andReturn
        @_.addCallback
        def showMe(result):
            return result
        return _



def open_session_store(reactor, db_uri, component_creators=(),
                       procurer_from_store=SessionProcurer):
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
            AlchimiaSessionStore, AccountBindingStorePlugin,
            lambda metadata, store: IPTrackingProcurer(
                metadata, store, procurer_from_store(next(
                    store.components_providing(ISessionStore)
                ))),
            AccountLoginAuthorizer,
        ] + list(component_creators)
    ).addCallback
    @opened
    def procurify(datastore):
        return next(datastore.components_providing(ISessionProcurer))
    return procurify



def tables(**kw):
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



def authorizer_for(authzn_for, schema=lambda txn, metadata: None):
    """
    Declare an SQL authorizer, implemented by a given function.  Used like so::

        @authorizer_for(Foo, tables(foo=[Column("bar", String())]))
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
        @implementer(ISQLAuthorizer, ISQLSchemaComponent)
        @attr.s
        class AnAuthorizer(object):
            metadata = attr.ib()
            datastore = attr.ib()

            authzn_for = an_authzn

            def initialize_schema(self, transaction):
                return schema(transaction, self.metadata)

            def authzn_for_session(self, session_store, transaction, session):
                return decorated(self.metadata, self.datastore, session_store,
                                 transaction, session)

        decorated.authorizer = AnAuthorizer
        return decorated
    return decorator
