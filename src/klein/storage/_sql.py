from alchimia import TWISTED_STRATEGY
import attr
from datetime import datetime
from attr import Factory

from binascii import hexlify
from os import urandom
from uuid import uuid4

from zope.interface import implementer
from twisted.python.components import Componentized

from twisted.logger import Logger

from klein.interfaces import (
    ISession, ISessionStore, NoSuchSession, ISimpleAccount,
    ISimpleAccountBinding, ISessionProcurer
)
from klein import SessionProcurer
from klein.storage.security import compute_key_text, check_and_reset

from sqlalchemy import (
    create_engine, MetaData, Table, Column, Boolean, String,
    ForeignKey, DateTime, UniqueConstraint
)
from sqlalchemy.schema import CreateTable
from sqlalchemy.exc import OperationalError, IntegrityError

from twisted.internet.defer import (
    Deferred, inlineCallbacks, returnValue
)
from twisted.python.failure import Failure

metadata = MetaData()

@implementer(ISession)
@attr.s
class SQLSession(object):
    """
    
    """
    identifier = attr.ib()
    is_confidential = attr.ib()
    authenticated_by = attr.ib()
    data = attr.ib(default=Factory(Componentized))



@implementer(ISessionStore)
@attr.s
class AlchimiaSessionStore(object):
    """
    
    """

    _session_table = Table(
        "session", metadata,
        Column("session_id", String(), primary_key=True, nullable=False),
        Column("confidential", Boolean(), nullable=False),
    )
    _session_ip_table = Table(
        "session_ip", metadata,
        Column("session_id", String(),
               ForeignKey("session.session_id", ondelete="CASCADE"),
               nullable=False),
        Column("ip_address", String(), nullable=False),
        Column("address_family", String(), nullable=False),
        Column("last_used", DateTime(), nullable=False),
        UniqueConstraint("session_id", "ip_address", "address_family"),
    )

    engine = attr.ib()
    session_plugins = attr.ib(default=Factory(list))

    @classmethod
    def create_with_schema(cls, db_url):
        """
        
        """
        from twisted.internet import reactor
        self = cls(create_engine(db_url, reactor=reactor,
                                 strategy=TWISTED_STRATEGY))
        @self.sql
        @inlineCallbacks
        def do(engine):
            for tbl in [self._session_table, self._session_ip_table]:
                try:
                    yield engine.execute(CreateTable(tbl))
                except OperationalError as oe:
                    print(oe)
            for data_interface, plugin_creator in self.session_plugin_registry:
                plugin = plugin_creator(self)
                try:
                    yield plugin.initialize_schema(engine)
                except OperationalError as oe:
                    print(oe)
                self.session_plugins.append((data_interface, plugin))
            returnValue(self)
        return do

    session_plugin_registry = []

    @classmethod
    def register_session_plugin(cls, data_interface):
        """
        
        """
        def registerer(wrapped):
            cls.session_plugin_registry.append((data_interface, wrapped))
            return wrapped
        return registerer


    _log = Logger()

    @inlineCallbacks
    def sql(self, callable):
        """
        
        """
        try:
            print("sql:running", callable)
            cxn = yield self.engine.connect()
            txn = yield cxn.begin()
            try:
                result = yield callable(cxn)
            except:
                # XXX rollback() and commit() might both also fail
                failure = Failure()
                yield txn.rollback()
                returnValue(failure)
            else:
                yield txn.commit()
                print("giving back", result, "from", callable)
                returnValue(result)
        finally:
            yield cxn.close()

    def sent_insecurely(self, tokens):
        """
        
        """
        @self.sql
        @inlineCallbacks
        def invalidate(engine):
            s = self._session_table
            for token in tokens:
                yield engine.execute(s.delete().where(
                    (s.c.session_id == token) &
                    (s.c.confidential == True)
                ))
        return invalidate


    def new_session(self, is_confidential, authenticated_by):
        @self.sql
        @inlineCallbacks
        def created(engine):
            identifier = hexlify(urandom(32))
            s = self._session_table
            yield engine.execute(s.insert().values(
                session_id=identifier,
                confidential=is_confidential,
            ))
            session = SQLSession(
                identifier=identifier,
                is_confidential=is_confidential,
                authenticated_by=authenticated_by,
            )
            yield self._populate(engine, session)
            returnValue(session)
        return created


    @inlineCallbacks
    def _populate(self, engine, session):
        """
        
        """
        for data_interface, plugin in self.session_plugins:
            session.data.setComponent(
                data_interface, (yield plugin.data_for_session(
                    self, engine, session, False)
                )
            )


    def load_session(self, identifier, is_confidential, authenticated_by):
        @self.sql
        @inlineCallbacks
        def loaded(engine):
            s = self._session_table
            result = yield engine.execute(
                s.select((s.c.session_id==identifier) &
                         (s.c.confidential==is_confidential)))
            results = yield result.fetchall()
            if not results:
                raise NoSuchSession()
            fetched_id = results[0][s.c.session_id]
            session = SQLSession(
                identifier=fetched_id,
                is_confidential=is_confidential,
                authenticated_by=authenticated_by,
            )
            yield self._populate(engine, session)
            returnValue(session)
        return loaded



@implementer(ISimpleAccountBinding)
@attr.s
class AccountSessionBinding(object):
    """
    (Stateless) binding between an account and a session, so that sessions can
    attach to, detach from, .
    """
    _session = attr.ib()
    _store = attr.ib()

    @inlineCallbacks
    def create_account(self, username, email, password):
        """
        Create a new account with the given username, email and password.

        @return: an L{Account} if one could be created, L{None} if one could
            not be.
        """
        computedHash = yield compute_key_text(password)
        @self._store.sql
        @inlineCallbacks
        def store(engine):
            new_account_id = unicode(uuid4())
            insert = (AccountBindingStorePlugin._account_table.insert()
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
        account = SQLAccount(self._store, account_id, username, email)
        returnValue(account)


    @inlineCallbacks
    def log_in(self, username, password):
        """
        Associate this session with a given user account, if the password
        matches.

        @param username:
        @type username:

        @param password:
        @type password:

        @rtype: L{Deferred} firing with L{IAccount} if we succeeded and L{None}
            if we failed.
        """
        print("log in to", repr(username))
        acc = AccountBindingStorePlugin._account_table
        @self._store.sql
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
        print("login in", account_id)

        def reset_password(new_pw_text):
            @self._store.sql
            def storenew(engine):
                a = AccountBindingStorePlugin._account_table
                return engine.execute(
                    a.update(a.c.account_id == account_id)
                    .values(password_blob=new_pw_text)
                )
            return storenew

        if (yield check_and_reset(stored_password_text,
                                  password,
                                  reset_password)):
            account = SQLAccount(self._store, account_id,
                                 row[acc.c.username], row[acc.c.email])
            yield account.add_session(self._session)
            returnValue(account)


    def authenticated_accounts(self):
        """
        Retrieve the accounts currently associated with this session.

        @return: L{Deferred} firing with a L{list} of accounts.
        """
        @self._store.sql
        @inlineCallbacks
        def retrieve(engine):
            ast = AccountBindingStorePlugin._account_session_table
            acc = AccountBindingStorePlugin._account_table
            result = (yield (yield engine.execute(
                ast.join(acc, ast.c.account_id == acc.c.account_id)
                .select(ast.c.session_id == self._session.identifier,
                        use_labels=True)
            )).fetchall())
            returnValue([
                SQLAccount(self._store, it[ast.c.account_id],
                           it[acc.c.username], it[acc.c.email])
                for it in result
            ])
        return retrieve


    def log_out(self):
        """
        Disassociate this session from any accounts it's logged in to.
        """
        @self._strptime.sql
        def retrieve(engine):
            ast = AccountBindingStorePlugin._account_session_table
            return engine.execute(ast.delete(
                ast.c.session_id == self._session.identifier
            ))
        return retrieve




@implementer(ISimpleAccount)
@attr.s
class SQLAccount(object):
    """
    
    """
    store = attr.ib()
    account_id = attr.ib()
    username = attr.ib()
    email = attr.ib()

    def add_session(self, session):
        """
        
        """
        @self.store.sql
        def createrow(engine):
            return engine.execute(
                AccountBindingStorePlugin._account_session_table
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
        @self.store.sql
        def change(engine):
            return engine.execute(
                AccountBindingStorePlugin._account_table.update()
                .where(account_id=self.account_id)
                .values(password_blob=computed_hash)
            )
        returnValue((yield change))

@AlchimiaSessionStore.register_session_plugin(ISimpleAccountBinding)
class AccountBindingStorePlugin(object):
    """
    
    """

    _account_table = Table(
        "account", metadata,
        Column("account_id", String(), primary_key=True,
               nullable=False),
        Column("username", String(), unique=True, nullable=False),
        Column("email", String(), nullable=False),
        Column("password_blob", String(), nullable=False),
    )

    _account_session_table = Table(
        "account_session", metadata,
        Column("account_id", String(),
               ForeignKey("account.account_id", ondelete="CASCADE")),
        Column("session_id", String(),
               ForeignKey("session.session_id", ondelete="CASCADE")),
        UniqueConstraint("account_id", "session_id"),
    )

    def __init__(self, store):
        """
        
        """
        self._store = store


    @inlineCallbacks
    def initialize_schema(self, engine):
        """
        
        """
        yield engine.execute(CreateTable(self._account_table))
        yield engine.execute(CreateTable(self._account_session_table))


    def data_for_session(self, session_store, cursor, session, existing):
        """
        
        """
        return AccountSessionBinding(session, session_store)



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


@implementer(ISessionStore)
@attr.s
class IPTrackingStore(object):
    """
    
    """
    store = attr.ib()
    request = attr.ib()

    @inlineCallbacks
    def _touch_session(self, session, style):
        """
        Update a session's IP address.  NB: different txn than the session
        generation; is it worth smashing these together?
        """
        session_id = session.identifier
        try:
            ip_address = (self.request.client.host or b"").decode("ascii")
        except:
            ip_address = u""
        print("updating session ip", ip_address)
        @self.store.sql
        @inlineCallbacks
        def touch(engine):
            print("here we go")
            address_family = (u"AF_INET6" if u":" in ip_address
                              else u"AF_INET")
            last_used = datetime.utcnow()
            sip = AlchimiaSessionStore._session_ip_table
            yield upsert(engine, sip,
                         dict(session_id=session_id,
                              ip_address=ip_address,
                              address_family=address_family),
                         dict(last_used=last_used))
            print("executed")
        yield touch
        print("returning", session, style)
        returnValue(session)

    def new_session(self, is_confidential, authenticated_by):
        return (self.store.new_session(is_confidential, authenticated_by)
                .addCallback(self._touch_session, "new"))

    def load_session(self, identifier, is_confidential, authenticated_by):
        return (self.store.load_session(identifier, is_confidential,
                                        authenticated_by)
                .addCallback(self._touch_session, "load"))

    def sent_insecurely(self, tokens):
        return self.store.sent_insecurely(tokens)


@implementer(ISessionProcurer)
@attr.s
class EventualProcurer(object):
    """
    
    """

    _eventual_store = attr.ib()

    @inlineCallbacks
    def procure_session(self, request, force_insecure=False,
                        always_create=True):
        """
        
        """
        store = yield self._eventual_store()
        procurer = SessionProcurer(IPTrackingStore(store, request))
        returnValue((yield procurer.procure_session(request, force_insecure)))



def open_session_store(db_uri):
    """
    Open a session store, returning a procurer that can procure sessions from
    it.

    @param db_uri: an SQLAlchemy database URI.

    @return: L{ISessionProcurer}
    """
    dstore = AlchimiaSessionStore.create_with_schema(db_uri)
    def eventually(store):
        eventually.store = store
    eventually.store = None
    dstore.addCallback(eventually)
    def _eventual_store():
        if eventually.store is not None:
            return eventually.store
        else:
            deferred = Deferred()
            @eventually.addCallback
            def set_store(ignored):
                deferred.callback(eventually.store)
            return deferred
    return EventualProcurer(_eventual_store)
