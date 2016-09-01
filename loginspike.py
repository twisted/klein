
from __future__ import print_function, unicode_literals, absolute_import

import attr
from attr import Factory

from uuid import uuid4
from binascii import hexlify
from os import urandom

from zope.interface import implementer, Interface

from twisted.web.template import tags, slot
from twisted.internet.defer import (
    execute, inlineCallbacks, returnValue, Deferred
)
from twisted.internet.threads import deferToThread
from twisted.python.components import Componentized
from twisted.python.compat import unicode

from klein import Klein, Plating, Form, SessionProcurer
from klein.interfaces import ISession, ISessionStore, NoSuchSession

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
                       href="#"),
                tags.ul(Class="nav navbar-nav")(
                    tags.li(Class="nav-item active")(
                        tags.a(Class="nav-link", href="#")(
                            "Home", tags.span(Class="sr-only")("(current)"))),
                    tags.li(Class="nav-item")(
                        tags.a("Login", Class="nav-link", href="/login")),
                    tags.li(Class="nav-item")(
                        tags.a("Signup", Class="nav-link", href="/signup")),
                    tags.form(Class="form-inline pull-xs-right")(
                        tags.input(Class="form-control", type="text",
                                   placeholder="Search"),
                        tags.button("Search", Class="btn btn-outline-success",
                                    type="submit")))),
            tags.div(Class="container")(
                slot(Plating.CONTENT)
            )
        )
    )
)

@style.routed(app.route("/"),
              tags.h1(slot('result')))
def root(request):
    return {"result": "hello world"}

@style.routed(app.route("/login"),
              tags.h1("Log In"))
def loginform(request):
    """
    
    """
    return {}

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
                        session_id text primary key,
                        confidential integer,
                    )
                """)
            except SQLError as sqle:
                print(sqle)
            for data_interface, plugin_creator in self.session_plugin_registry:
                plugin = plugin_creator(self)
                plugin.initialize_schema(cursor)
                self.session_plugins.append(data_interface, plugin)
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
        def async():
            with self.connectionFactory() as connection:
                return execute(lambda: callable(connection.cursor()))
        return deferToThread(async)


    def sent_insecurely(self, tokens):
        """
        
        """
        @self.sql
        def invalidate(c):
            for token in tokens:
                c.execute(
                    """
                    delete from session where session_id = ?
                    and confidential = 1;
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
                session.setComponent(
                    data_interface, plugin.data_for_session(self, session,
                                                            False)
                )
            return session
        return created


    def load_session(self, identifier, is_confidential, authenticated_by):
        @self.sql
        def loaded(c):
            c.execute(
                """
                select session_id from session where session_id = ?
                and confidential = ?;
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
                session.setComponent(
                    data_interface, plugin.data_for_session(self, session,
                                                            True)
                )
            return session
        return loaded


class IAccountManager(Interface):
    """
    
    """

class ISQLSessionDataPlugin(Interface):
    """
    
    """

    def initialize_schema(cursor):
        """
        
        """

    def data_for_session(session_store, session, existing):
        """
        
        """




@SQLiteSessionStore.register_session_plugin(IAccountManager)
@implementer(ISQLSessionDataPlugin)
class AccountManagerManager(object):
    """
    
    """
    def __init__(self, manager):
        """
        
        """
        self._manager = manager


    def initialize_schema(self, cursor):
        """
        
        """
        try:
            cursor.execute("""
                create table account (
                    account_id text primary key,
                    username text unique,
                    email text,
                    scrypt_hash text,
                );
                create table account_session (
                    account_id text,
                    session_id text
                );
                """)
        except SQLError as se:
            print(se)


    def data_for_session(self, session_store, session, existing):
        """
        
        """
        return AccountSessionBinding(session, session_store)



from txscrypt import computeKey, checkPassword

@attr.s
class Account(object):
    """
    
    """
    store = attr.ib()
    account_id = attr.ib()

    @inlineCallbacks
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


    @inlineCallbacks
    def change_password(self, new_password):
        """
        
        """
        computedHash = yield computeKey(new_password)
        @self.store.sql
        def change(cursor):
            cursor.execute("""
            update account set scrypt_hash = ?
            where account_id = ?
            """, self.account_id, computedHash)
        yield change




@implementer(IAccountManager)
@attr.s
class AccountSessionBinding(object):
    """
    
    """
    _session = attr.ib()
    _store = attr.ib()

    @inlineCallbacks
    def create_account(self, username, email, password):
        """
        
        """
        computedHash = yield computeKey(password)
        @self._store.sql
        def store(cursor):
            new_account_id = unicode(uuid4())
            cursor.execute("""
            insert into account (
                account_id, username, email, scrypt_hash
            ) values (
                ?, ?, ?, ?
            );
            """, [new_account_id, username, email, computedHash])
            return new_account_id
        account = Account(self._store, (yield store))
        yield account.add_session(self._session)
        returnValue(account)


    @inlineCallbacks
    def log_in(self, username, password):
        """
        
        """
        @self._store.sql
        def retrieve(cursor):
            return list(cursor.execute(
                """
                select account_id, scrypt_hash from account
                where username = ?
                """,
                username
            ))[0]
        account_id, scrypt_hash = yield retrieve
        passed = yield checkPassword(scrypt_hash, password)
        if passed:
            account = Account(self._store, username)
            yield account.add_session(self._session)
            returnValue(account)



@implementer(ISession)
@attr.s
class SQLSession(object):
    """
    
    """
    identifier = attr.ib()
    is_confidential = attr.ib()
    authenticated_by = attr.ib()
    data = attr.ib(default=Factory(Componentized))

    def save(self):
        """
        
        """


@attr.s
class EventualProcurer(object):
    """
    
    """

    _eventual_manager = attr.ib()
    _request = attr.ib()

    @inlineCallbacks
    def procure_session(self, force_insecure=False):
        """
        
        """
        manager = yield self._eventual_manager()
        procurer = SessionProcurer(manager, self._request)
        returnValue((yield procurer.procure_session(force_insecure)))



class EventualSessionManager(object):
    """
    
    """
    def __init__(self, manager_deferred):
        """
        
        """
        self._manager_deferred = manager_deferred
        self._manager = None
        @manager_deferred.addCallback
        def set_manager(result):
            self._manager = result
            return result

    def _eventual_manager(self):
        """
        
        """
        if self._manager is not None:
            return self._manager
        else:
            deferred = Deferred()
            @self._manager_deferred.addCallback
            def set_manager(result):
                deferred.callback(result)
                return result
            return deferred

    def procurer(self, request):
        """
        
        """
        if self._manager is None:
            return EventualProcurer(self._eventual_manager, request)
        else:
            return SessionProcurer(self._manager, request)

session_manager = EventualSessionManager(
    SQLiteSessionStore.create_with_schema(lambda: connect("sessions.sqlite"))
)

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
         style="margin: auto; width: 400px;"
         "margin-top: 100px")
      (slot("csrf_here"),
       tags.div(Class="form-group row")
       (tags.label(For="email",
                        Class="col-sm-3 col-form-label")("Email: "),
        tags.div(Class="col-sm-8")(
            tags.input(type="email", Class="form-control",
                       autofocus="true",
                       id="email", placeholder="Email")
        )),
       tags.div(Class="form-group row")
       (tags.label(For="username",
                        Class="col-sm-3 col-form-label")("Username: "),
        tags.div(Class="col-sm-8")(
            tags.input(type="text", Class="form-control",
                       autofocus="true",
                       id="username", placeholder="Username")
        )),
       tags.div(Class="form-group row")
       (tags.label(For="anPassword",
                   Class="col-sm-3 col-form-label")("Password: "),
        tags.div(Class="col-sm-8")(
            tags.input(type="password", Class="form-control",
                       id="anPassword", placeholder=""))),
       tags.div(Class="form-group row")
       (tags.div(Class="offset-sm-3 col-sm-8")
        (tags.button(type="submit", Class="btn btn-primary col-sm-4")
         ("Log In")))))]
)
def signup_page(request, the_form):
    """
    
    """
    return {
        "csrf_here": the_form.csrf()
    }



@style.routed(
    signup.handler(app.route("/signup", methods=["POST"])),
    [tags.h1("U SIGNED UP YAY")]
)
def do_signup(request, username, email, password):
    """
    
    """
    mgr = (request.getComponent(ISession).data.getComponent(IAccountManager))
    mgr.create_account(username, email, password)
    return {}



app.run("localhost", 8976)
