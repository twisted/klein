
from __future__ import print_function, unicode_literals, absolute_import

import attr
from attr import Factory

from uuid import uuid4
from binascii import hexlify
from os import urandom
from datetime import datetime

from zope.interface import implementer, Interface

from twisted.web.template import tags, slot
from twisted.internet.defer import (
    inlineCallbacks, returnValue, Deferred
)
from twisted.internet.threads import deferToThread
from twisted.python.components import Componentized
from twisted.python.compat import unicode

from klein import Klein, Plating, Form, SessionProcurer
from klein.interfaces import ISession, ISessionStore, NoSuchSession

from sqlite3 import Error as SQLError, connect

@implementer(ISessionStore)
@attr.s
class SQLiteSessionStore(object):
    """
    
    """
    connectionFactory = attr.ib()
    session_plugins = attr.ib(default=Factory(list))

    @classmethod
    def create_with_schema(cls, connectionFactory):
        """
        
        """
        self = cls(connectionFactory)
        @self.sql
        def do(cursor):
            try:
                cursor.execute(
                    """
                    create table session (
                        session_id text primary key not null,
                        confidential integer not null
                    )
                    """
                )
                cursor.execute("""
                    create table session_ip (
                        session_id text
                            references session(session_id)
                            on delete cascade,
                        ip_address text not null,
                        address_family text not null,
                        last_used timestamp not null,
                        unique(session_id, ip_address, address_family)
                    )
                    """
                )
            except SQLError as sqle:
                print("sqle:", sqle)
            for data_interface, plugin_creator in self.session_plugin_registry:
                plugin = plugin_creator(self)
                plugin.initialize_schema(cursor)
                self.session_plugins.append((data_interface, plugin))
            return self
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


    def sql(self, callable):
        """
        
        """
        print("sql:running", callable)
        @deferToThread
        def async():
            with self.connectionFactory() as connection:
                return callable(connection.cursor())
        return async


    def sent_insecurely(self, tokens):
        """
        
        """
        @self.sql
        def invalidate(c):
            for token in tokens:
                c.execute(
                    """
                    delete from session where session_id = ?
                    and confidential = 1
                    """, [token]
                )
        return invalidate


    def new_session(self, is_confidential, authenticated_by):
        @self.sql
        def created(c):
            identifier = hexlify(urandom(32))
            c.execute(
                """
                insert into session values (
                    ?, ?
                )
                """, [identifier, is_confidential]
            )
            session = SQLSession(
                identifier=identifier,
                is_confidential=is_confidential,
                authenticated_by=authenticated_by,
            )
            for data_interface, plugin in self.session_plugins:
                session.data.setComponent(
                    data_interface, plugin.data_for_session(self, c,
                                                            session, False)
                )
            return session
        return created


    def load_session(self, identifier, is_confidential, authenticated_by):
        @self.sql
        def loaded(c):
            c.execute(
                """
                select session_id from session where session_id = ?
                and confidential = ?
                """, [identifier, int(is_confidential)]
            )
            results = list(c.fetchall())
            if not results:
                raise NoSuchSession()
            [[fetched_id]] = results
            session = SQLSession(
                identifier=fetched_id,
                is_confidential=is_confidential,
                authenticated_by=authenticated_by,
            )
            for data_interface, plugin in self.session_plugins:
                session.data.setComponent(
                    data_interface, plugin.data_for_session(self, c, session,
                                                            True)
                )
            return session
        return loaded



@implementer(ISessionStore)
@attr.s
class IPTrackingStore(object):
    """
    
    """
    store = attr.ib()
    request = attr.ib()

    @inlineCallbacks
    def _touch_session(self, session):
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
        def touch(cursor):
            print("here we go")
            address_family = (u"AF_INET6" if u":" in ip_address
                              else u"AF_INET")
            last_used = datetime.utcnow()
            cursor.execute("""
                insert or replace into session_ip
                (session_id, ip_address, address_family, last_used)
                values
                (?, ?, ?, ?)
            """, [session_id, ip_address, address_family, last_used])
            print("executed")
        yield touch
        print("returning", session)
        returnValue(session)

    def new_session(self, is_confidential, authenticated_by):
        return (self.store.new_session(is_confidential, authenticated_by)
                .addCallback(self._touch_session))

    def load_session(self, identifier, is_confidential, authenticated_by):
        return (self.store.load_session(identifier, is_confidential,
                                        authenticated_by)
                .addCallback(self._touch_session))

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
    def __init__(self, store):
        """
        
        """
        self._store = store


    def initialize_schema(self, cursor):
        """
        
        """
        try:
            cursor.execute("""
                create table account (
                    account_id text primary key not null,
                    username text unique not null,
                    email text not null,
                    password_blob text not null
                )
                """)
            cursor.execute("""
                create table account_session (
                    account_id text references account(account_id)
                        on delete cascade,
                    session_id text references session(session_id)
                        on delete cascade,
                    unique(account_id, session_id)
                )
            """)
        except SQLError as se:
            print(se)


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
        def createrow(cursor):
            cursor.execute(
                """
                insert into account_session
                (account_id, session_id) values (?, ?)
                """, [self.account_id, session.identifier]
            )
        return createrow


    @inlineCallbacks
    def change_password(self, new_password):
        """
        
        """
        computedHash = yield computeKey(password_bytes(new_password))
        @self.store.sql
        def change(cursor):
            cursor.execute("""
            update account set password_blob = ?
            where account_id = ?
            """, self.account_id, computedHash)
        yield change



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
        def store(cursor):
            new_account_id = unicode(uuid4())
            cursor.execute("""
            insert into account (
                account_id, username, email, password_blob
            ) values (
                ?, ?, ?, ?
            )
            """, [new_account_id, username, email, computedHash])
            return new_account_id
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
        def retrieve(cursor):
            return list(cursor.execute(
                """
                select account_id, password_blob from account
                where username = ?
                """,
                [username]
            ))
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
                def storenew(cursor):
                    cursor.execute("""
                    update account set password_blob = ? where account_id = ?
                    """, [new_key, account_id])

            account = Account(self._store, account_id)
            yield account.add_session(self._session)
            returnValue(account)


    def authenticated_accounts(self):
        """
        Retrieve the accounts currently associated with this session.

        @return: L{Deferred} firing with a L{list} of accounts.
        """
        @self._store.sql
        def retrieve(cursor):
            return [
                Account(account_id)
                for [account_id] in
                cursor.execute(
                    """
                    select account_id from account_session where session_id = ?
                    """,
                )
            ]
        return retrieve


    def log_out(self):
        """
        Disassociate this session from any accounts it's logged in to.
        """
        @self._store.sql
        def retrieve(cursor):
            cursor.execute(
                """
                delete from account_session where session_id = ?
                """, [self._session.session_id]
            )
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
                        tags.button("Logout", Class="btn")
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


session_manager = EventualSessionManager(
    SQLiteSessionStore.create_with_schema(lambda: connect("sessions.sqlite"))
)

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
    mgr = (request.getComponent(ISession).data.getComponent(ISimpleAccountBinding))
    account_object = yield mgr.create_account(username, email, password)
    returnValue({
        "signup_active": "active",
        "account_id": account_object.account_id,
    })



app.run("localhost", 8976)
