
from __future__ import print_function, unicode_literals, absolute_import

import attr
from attr import Factory

from alchimia import TWISTED_STRATEGY

from sqlalchemy import (
    create_engine, MetaData, Table, Column, Boolean, String,
    ForeignKey, DateTime, UniqueConstraint
)
from sqlalchemy.exc import OperationalError, IntegrityError

from sqlalchemy.schema import CreateTable

from uuid import uuid4
from binascii import hexlify
from os import urandom
from datetime import datetime

from zope.interface import implementer, Interface

from twisted.web.template import tags, slot
from twisted.internet.defer import (
    inlineCallbacks, returnValue, Deferred
)
from twisted.python.components import Componentized
from twisted.python.compat import unicode
from twisted.logger import Logger

from klein import Klein, Plating, Form, SessionProcurer
from klein.interfaces import ISession, ISessionStore, NoSuchSession

from sqlite3 import connect

metadata = MetaData()

@implementer(ISessionStore)
@attr.s
class SQLiteSessionStore(object):
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
                self._log.failure("while executing sql {callable}",
                                  callable=callable)
                # XXX rollback() and commit() might both also fail
                yield txn.rollback()
            else:
                yield txn.commit()
        finally:
            cxn.close()
        returnValue(result)

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
            sip = SQLiteSessionStore._session_ip_table
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



class ISimpleAccountBinding(Interface):
    """
    Data-store agnostic account / session binding manipulation API for "simple"
    accounts - i.e. those using username, password, and email address as a
    method to authenticate a user.

    This goes into a user-authentication-capable L{ISession} object's C{data}
    attribute as a component.
    """

    def log_in(username, password):
        """
        Attach the session this is a component of to an account with the given
        username and password, if the given username and password correctly
        authenticate a principal.
        """

    def authenticated_accounts():
        """
        Retrieve the accounts currently associated with the session this is a
        component of.

        @return: L{Deferred} firing with a L{list} of accounts.
        """

    def log_out():
        """
        Disassociate the session this is a component of from any accounts it's
        logged in to.
        """

    def create_account(username, email, password):
        """
        Create a new account with the given username, email and password.
        """



class ISQLSessionDataPlugin(Interface):
    """
    
    """

    def initialize_schema(cursor):
        """
        
        """


    def data_for_session(session_store, cursor, session, existing):
        """
        Get a data object to put onto the session.  This is run in the database
        thread, but at construction time, so it is not concurrent with any
        other access to the session.
        """



@SQLiteSessionStore.register_session_plugin(ISimpleAccountBinding)
@implementer(ISQLSessionDataPlugin)
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



from unicodedata import normalize
from txscrypt import computeKey, checkPassword

def password_bytes(password_text):
    """
    Convert a textual password into some bytes.
    """
    return normalize("NFKD", password_text).encode("utf-8")



@attr.s
class Account(object):
    """
    
    """
    store = attr.ib()
    account_id = attr.ib()

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
        
        """
        computedHash = yield computeKey(password_bytes(new_password))
        @self.store.sql
        def change(engine):
            return engine.execute(
                AccountBindingStorePlugin._account_table.update()
                .where(account_id=self.account_id)
                .values(password_blob=computedHash)
            )
        returnValue((yield change))



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
        """
        computedHash = yield computeKey(password_bytes(password))
        @self._store.sql
        @inlineCallbacks
        def store(engine):
            new_account_id = unicode(uuid4())
            yield engine.execute(
                AccountBindingStorePlugin._account_table.insert()
                .values(account_id=new_account_id,
                        username=username, email=email,
                        password_blob=computedHash)
            )
            returnValue(new_account_id)
        account = Account(self._store, (yield store))
        yield account.add_session(self._session)
        returnValue(account)


    @inlineCallbacks
    def log_in(self, username, password):
        """
        Associate this session with a given user account, if the password
        matches.

        @rtype: L{Deferred} firing with L{IAccount} if we succeeded and L{None}
            if we failed.
        """
        print("log in to", repr(username))
        @self._store.sql
        @inlineCallbacks
        def retrieve(engine):
            result = yield engine.execute(
                AccountSessionBinding._account_table.select(
                    AccountSessionBinding._account_table.username == username
                )
            )
            returnValue((yield result.fetchall()))
        accounts_info = yield retrieve
        if not accounts_info:
            # no account, bye
            returnValue(None)
        [[account_id, password_blob]] = accounts_info
        print("login in", account_id, password_blob)
        pw_bytes = password_bytes(password)
        if (yield checkPassword(password_blob, pw_bytes)):
            # Password migration!  Does txscrypt have an awesome *new* hash it
            # wants to give us?  Store it.
            new_key = yield computeKey(pw_bytes)
            if new_key != password_blob:
                @self._store.sql
                def storenew(engine):
                    return engine.execute(
                        AccountBindingStorePlugin._account_table.update()
                        .values(password_blob=new_key, account_id=account_id)
                    )
                yield storenew

            account = Account(self._store, account_id)
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
            returnValue([
                Account(self._store, it[ast.c.account_id])
                for it in
                (yield (yield engine.execute(
                    ast.select(ast.c.session_id==self._session.identifier)
                )).fetchall())
            ])
        return retrieve


    def log_out(self):
        """
        Disassociate this session from any accounts it's logged in to.
        """
        @self._store.sql
        def retrieve(engine):
            ast = AccountBindingStorePlugin._account_session_table
            return engine.execute(ast.delete(self._session.identifier))
        return retrieve



@implementer(ISession)
@attr.s
class SQLSession(object):
    """
    
    """
    identifier = attr.ib()
    is_confidential = attr.ib()
    authenticated_by = attr.ib()
    data = attr.ib(default=Factory(Componentized))


@attr.s
class EventualProcurer(object):
    """
    
    """

    _eventual_store = attr.ib()
    _request = attr.ib()

    @inlineCallbacks
    def procure_session(self, force_insecure=False):
        """
        
        """
        store = yield self._eventual_store()
        procurer = SessionProcurer(IPTrackingStore(store, self._request),
                                   self._request)
        returnValue((yield procurer.procure_session(force_insecure)))



class EventualSessionManager(object):
    """
    
    """
    def __init__(self, store_deferred):
        """
        
        """
        self._store_deferred = store_deferred
        self._store = None
        @store_deferred.addCallback
        def set_store(result):
            self._store = result
            return result

    def _eventual_store(self):
        """
        
        """
        if self._store is not None:
            return self._store
        else:
            deferred = Deferred()
            @self._store_deferred.addCallback
            def set_store(result):
                deferred.callback(result)
                return result
            return deferred

    def procurer(self, request):
        """
        
        """
        if self._store is None:
            print("mngr:none")
            return EventualProcurer(self._eventual_store, request)
        else:
            print("hasmanager:", self._store)
            return SessionProcurer(IPTrackingStore(self._store, request),
                                   request)

# ^^^  framework   ^^^^
# ---  cut here    ----
# vvvv application vvvv

app = Klein()

def bootstrap(x):
    return "https://maxcdn.bootstrapcdn.com/bootstrap/4.0.0-alpha.3/" + x

style = Plating(
    tags=tags.html(
        tags.head(
            tags.link(rel="stylesheet",
                      href=bootstrap("css/bootstrap.min.css"),
                      integrity="sha384-MIwDKRSSImVFAZCVLtU0LMDdON6KVCrZHyVQQ"
                      "j6e8wIEJkW4tvwqXrbMIya1vriY",
                      crossorigin="anonymous"),
            # tags.script(
            #     src=bootstrap("js/bootstrap.min.js"),
            #     integrity=("sha384-ux8v3A6CPtOTqOzMKiuo3d/DomGaaClxFYdCu2HPM"
            #                "BEkf6x2xiDyJ7gkXU0MWwaD"),
            #     crossorigin="anonymous"
            # ),
            tags.title("hooray")
        ),
        tags.body(
            tags.nav(Class="navbar navbar-light bg-faded")(
                tags.a("Navbar", Class="navbar-brand",
                       href="/"),
                tags.ul(Class="nav navbar-nav")(
                    tags.li(Class=["nav-item ", slot("home_active")])(
                        tags.a(Class="nav-link",
                               href="/")(
                            "Home", tags.span(Class="sr-only")("(current)"))),
                    tags.li(Class=["nav-item ", slot("login_active")])(
                        tags.a("Login",
                               Class="nav-link",
                               href="/login")),
                    tags.li(Class=["nav-item ", slot("signup_active")])(
                        tags.a("Signup", Class="nav-link", href="/signup")),
                    tags.li(Class="nav-item pull-xs-right",
                            render="if_logged_in")(
                                tags.form(render="logout_csrf",
                                          action="/logout",
                                          method="POST")(
                                    tags.button("Logout", Class="btn"),
                                )
                            ),
                    tags.li(
                        tags.form(Class="form-inline pull-xs-right")(
                        tags.input(Class="form-control", type="text",
                                   placeholder="Search"),
                        tags.button("Search", Class="btn btn-outline-success",
                                    type="submit"))
                    )
                )),
            tags.div(Class="container")(
                slot(Plating.CONTENT)
            )
        )
    ),
    defaults={
        "home_active": "",
        "login_active": "",
        "signup_active": "",
    }
)


@style.routed(app.route("/"),
              tags.h1(slot('result')))
def root(request):
    return {
        "result": "hello world",
        "home_active": "active"
    }

def db_connect():
    c = connect("sessions.sqlite")
    c.execute("PRAGMA foreign_keys = ON")
    return c

session_manager = EventualSessionManager(
    SQLiteSessionStore.create_with_schema("sqlite:///sessions.sqlite")
)

logout = Form(dict(), session_manager.procurer)

@logout.handler(app.route("/logout", methods=["POST"]))
@inlineCallbacks
def bye(request):
    """
    Log out.
    """
    from twisted.web.util import Redirect
    yield ISimpleAccountBinding(ISession(request).data).log_out()
    returnValue(Redirect(b"/"))



@style.render
@inlineCallbacks
def if_logged_in(request, tag):
    """
    
    """
    try:
        session = yield session_manager.procurer(request).procure_session()
    except ValueError:
        # XXX too broad an exception, let's have something more specific in the
        # procurer
        returnValue(u"")
    binding = session.data.getComponent(ISimpleAccountBinding)
    accounts = yield binding.authenticated_accounts()
    if accounts:
        returnValue(tag)
    else:
        returnValue(u"")


@logout.renderer(style.render, "/logout")
def logout_csrf(request, tag, form):
    """
    
    """
    csrft = form.csrf()
    print("rendering", csrft)
    return tag(csrft)

login = Form(
    dict(
        username=Form.text(),
        password=Form.password(),
    ),
    session_manager.procurer
)

@style.routed(
    login.renderer(app.route("/login", methods=["GET"]), action="/login",
                   argument="login_form"),
    [tags.h1("Log In....."),
     tags.div(Class="container")
     (tags.form(
         style="margin: auto; width: 400px; margin-top: 100px",
         action="/login",
         method="POST")
      (slot("csrf_here"),
       tags.div(Class="form-group row")
       (tags.label(For="username",
                        Class="col-sm-3 col-form-label")("Username: "),
        tags.div(Class="col-sm-8")(
            tags.input(type="text", Class="form-control",
                       autofocus="true",
                       name="username", placeholder="Username")
        )),
       tags.div(Class="form-group row")
       (tags.label(For="anPassword",
                   Class="col-sm-3 col-form-label")("Password: "),
        tags.div(Class="col-sm-8")(
            tags.input(type="password", Class="form-control",
                       name="password", placeholder=""))),
       tags.div(Class="form-group row")
       (tags.div(Class="offset-sm-3 col-sm-8")
        (tags.button(type="submit", Class="btn btn-primary col-sm-4")
         ("Log In")))))]
)
def loginform(request, login_form):
    """
    
    """
    return {
        "login_active": "active",
        "csrf_here": login_form.csrf()
    }

@style.routed(login.handler(app.route("/login", methods=["POST"])),
              [tags.h1("u log in 2 ", slot("new_account_id"))])
@inlineCallbacks
def dologin(request, username, password):
    """
    
    """
    print('login???', request.args, username)
    manager = ISession(request).data.getComponent(ISimpleAccountBinding)
    account = yield manager.log_in(username, password)
    if account is None:
        an_id = 'naaaahtthiiiing'
    else:
        an_id = account.account_id
    returnValue({
        "login_active": "active",
        "new_account_id": an_id,
    })



signup = Form(
    dict(
        username=Form.text(),
        email=Form.text(),
        password=Form.password(),
    ),
    session_manager.procurer
)

@style.routed(
    signup.renderer(app.route("/signup", methods=["GET"]),
                    action="/signup",
                    argument="the_form"),
    [tags.h1("Sign Up"),
     tags.div(Class="container")
     (tags.form(
         style="margin: auto; width: 400px; margin-top: 100px",
         action="/signup",
         method="POST")
      (slot("csrf_here"),
       tags.div(Class="form-group row")
       (tags.label(For="email",
                   Class="col-sm-3 col-form-label")("Email: "),
        tags.div(Class="col-sm-8")(
            tags.input(type="email", Class="form-control",
                       autofocus="true",
                       name="email", placeholder="Email")
        )),
       tags.div(Class="form-group row")
       (tags.label(For="username",
                        Class="col-sm-3 col-form-label")("Username: "),
        tags.div(Class="col-sm-8")(
            tags.input(type="text", Class="form-control",
                       autofocus="true",
                       name="username", placeholder="Username")
        )),
       tags.div(Class="form-group row")
       (tags.label(For="anPassword",
                   Class="col-sm-3 col-form-label")("Password: "),
        tags.div(Class="col-sm-8")(
            tags.input(type="password", Class="form-control",
                       name="password", placeholder=""))),
       tags.div(Class="form-group row")
       (tags.div(Class="offset-sm-3 col-sm-8")
        (tags.button(type="submit", Class="btn btn-primary col-sm-4")
         ("Sign Up")))))]
)
def signup_page(request, the_form):
    """
    
    """
    return {
        "csrf_here": the_form.csrf(),
        "signup_active": "active"
    }



@style.routed(
    signup.handler(app.route("/signup", methods=["POST"])),
    [tags.h1("U SIGNED UP YAY"),
     tags.p("Now ", tags.a(href="/login")("log in"), ".")]
)
@inlineCallbacks
def do_signup(request, username, email, password):
    """
    
    """
    returnValue({
        "signup_active": "active",
        "account_id": (yield (
            request.getComponent(ISession).data
            .getComponent(ISimpleAccountBinding)
            .create_account(username, email, password)
        )).account_id,
    })


if __name__ == '__main__':
    app.run("localhost", 8976)
