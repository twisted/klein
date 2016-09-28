from alchimia import TWISTED_STRATEGY
import attr
from attr import Factory

from zope.interface import implementer
from twisted.python.components import Componentized

from klein.interfaces import ISession, ISessionStore, NoSuchSession
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Boolean, String,
    ForeignKey, DateTime, UniqueConstraint, CreateTable
)

from sqlalchemy.exc import OperationalError

from twisted.internet.defer import (
    inlineCallbacks, returnValue
)

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


