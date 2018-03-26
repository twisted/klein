
from __future__ import print_function, unicode_literals, absolute_import


from sqlalchemy import Table, MetaData
from sqlalchemy.schema import CreateTable
from sqlalchemy.exc import OperationalError

from twisted.web.iweb import IRequest
from twisted.web.template import tags, slot, Tag
from twisted.internet.defer import Deferred, inlineCallbacks, returnValue

from typing import Dict, Any

from klein import (Klein, Plating, Form, Field, RenderableForm, Requirer,
                   Authorization)
from klein.interfaces import (
    ISimpleAccountBinding, SessionMechanism, ISimpleAccount, ISessionProcurer,
    ISessionStore, ISession
)

from klein.storage.sql import (
    procurerFromDataStore, authorizerFor, SessionSchema, DataStore, Transaction
)

from twisted.web.util import Redirect

# silence flake8 for type-checking
(ISessionProcurer, Deferred, IRequest, Dict, Tag, Any,
 RenderableForm, ISessionStore)

app = Klein()

def bootstrap(x):
    # type: (str) -> str
    return "https://maxcdn.bootstrapcdn.com/bootstrap/4.0.0/" + x

requirer = Requirer()

style = Plating(
    tags=tags.html(
        tags.head(
            tags.link(rel="stylesheet",
                      href=bootstrap("css/bootstrap.min.css"),
                      crossorigin="anonymous"),
            # tags.script(
            #     src=bootstrap("js/bootstrap.min.js"),
            #     crossorigin="anonymous"
            # ),
            tags.title("hooray")
        ),
        tags.body(
            tags.nav(Class="navbar navbar-expand-lg navbar-light bg-light")(
                tags.a("Navbar", Class="navbar-brand",
                       href="/"),
                tags.ul(Class="nav navbar-nav")(
                    tags.li(Class=["nav-item ", slot("homeActive")])(
                        tags.a(Class="nav-link",
                               href="/")(
                                   "Home", tags.span(Class="sr-only")("(current)"))),
                    tags.li(render="ifLoggedOut",
                            Class=["nav-item ", slot("loginActive")])(
                                    tags.a("Login",
                               Class="nav-link",
                                           href="/login")),
                    tags.li(render="ifLoggedOut",
                            Class=["nav-item ", slot("signupActive")])(
                                    tags.a("Signup", Class="nav-link", href="/signup")),
                ),
                tags.ul(Class="nav navbar-nav ml-auto")(
                    tags.transparent(render="ifLoggedIn")(
                        tags.li(Class="nav-item")(
                            tags.a(Class="nav-link active",
                                   href=[
                                       "/u/",
                                       tags.transparent(render="username")
                                   ],
                                   render="username")
                        ),
                        tags.li(Class=["nav-item ", slot("sessionsActive")])(
                            tags.a("Sessions", Class="nav-link",
                                   href="/sessions")),
                        tags.li(Class="nav-item pull-xs-right")(
                            tags.form(render="logoutGlue",
                                      action="/logout",
                                      method="POST")(
                                          tags.button("Logout", Class="btn"),
                                      )
                        )
                    ),
                    tags.li(
                        tags.form(Class="form-inline", action="/search")(
                            tags.input(Class="form-control", type="text",
                                       name="q",
                                       placeholder="Search"),
                            tags.button("Search",
                                        Class="btn btn-outline-success",
                                        type="submit")
                        )
                    )
                ),
            ),
            tags.div(Class="container")(
                slot(Plating.CONTENT)
            )
        )
    ),
    defaults={
        "homeActive": "",
        "loginActive": "",
        "signupActive": "",
        "sessionsActive": "",
    }
)

from sqlalchemy import Column, String, ForeignKey

import attr

@attr.s
class Chirper(object):
    transaction = attr.ib(type=Transaction)
    account = attr.ib(type=ISimpleAccount)
    chirpTable = attr.ib(type=Table)

    def chirp(self, value):
        # type: (str) -> Deferred
        chirpTable = self.chirpTable
        return self.transaction.execute(chirpTable.insert().values(
                account_id=self.account.accountID,
                chirp=value
            ))

appMetadata = MetaData()
sessionSchema = SessionSchema.withMetadata(appMetadata)
chirpTable = Table(
    'chirp', appMetadata,
    Column("account_id", String(),
           ForeignKey(sessionSchema.account.c.account_id)),
    Column("chirp", String())
)

@authorizerFor(Chirper)
@inlineCallbacks
def authorizeChirper(session_store, transaction, session):
    # type: (ISessionStore, Transaction, ISession) -> Deferred
    account = (yield session.authorize([ISimpleAccount]))[ISimpleAccount]
    if account is not None:
        returnValue(Chirper(transaction, account, chirpTable))



@attr.s
class ChirpReader(object):
    transaction = attr.ib(type=Transaction)

    @inlineCallbacks
    def readChirps(self, username):
        # type: (str) -> Deferred
        result = yield ((yield self.transaction.execute(chirpTable.select(
            (chirpTable.c.account_id ==
             sessionSchema.account.c.account_id) &
            (sessionSchema.account.c.username == username)
        ))).fetchall())
        returnValue([row[chirpTable.c.chirp] for row in result])

@authorizerFor(ChirpReader)
def authForReading(sessionStore, transaction, session):
    # type: (ISessionStore, Transaction, ISession) -> ChirpReader
    return ChirpReader(transaction)


from twisted.internet import reactor
dataStore = DataStore.open(reactor, "sqlite:///sessions.sqlite")

from twisted.logger import Logger
log = Logger()
@dataStore.transact
@inlineCallbacks
def initSchema(transaction):
    # type: (Transaction) -> Deferred
    """
    Initialize the application's schema in the worst possible way.
    """
    for table in appMetadata.sorted_tables:
        try:
            yield transaction.execute(CreateTable(table))
        except OperationalError:
            pass
        else:
            log.info("created {table}", table=table)

initSchema.addErrback(log.failure)

procurer = procurerFromDataStore(
    dataStore,
    [authorizeChirper.authorizer, authForReading.authorizer]
)  # type: ISessionProcurer

@requirer.prerequisite([ISession])
def getSessionProcurer(request):
    # type: (IRequest) -> ISessionProcurer
    return procurer.procureSession(request)

@requirer.require(
    style.routed(app.route("/u/<user>"),
                 [tags.h1("chirps for ", slot("user")),
                  tags.div(Class="chirp", render="chirps:list")(
                      slot("item"),
                  )]),
    reader=Authorization(ChirpReader)
)
@inlineCallbacks
def readSomeChirps(request, user, reader):
    # type: (IRequest, str, ChirpReader) -> Deferred
    chirps = yield reader.readChirps(user)
    returnValue({
        "user": user,
        "chirps": chirps,
    })


@requirer.require(
    app.route("/chirp", methods=["POST"]),
    value=Field.text(),
    chirper=Authorization(Chirper),
)
@inlineCallbacks
def addChirp(request, chirper, value):
    # type: (IRequest, Chirper, str) -> Deferred
    yield chirper.chirp(value)
    returnValue(Redirect(b"/"))


@requirer.require(
    style.routed(app.route("/"),
                 [tags.h1(slot('result')),
                  tags.div(slot("chirp_form"))]),
    account=Authorization.optional(ISimpleAccount),
    chirp_form=Form.rendererFor(addChirp, "/chirp")
)
def root(request, chirp_form, account):
    # type: (IRequest, Chirper, ISimpleAccount) -> Dict
    return {
        "result": "hello world",
        "homeActive": "active",
        "chirp_form": chirp_form if account is not None else u"",
    }


@requirer.require(
    app.route("/logout", methods=["POST"]),
    binding=Authorization(ISimpleAccountBinding)
)
@inlineCallbacks
def bye(request, binding):
    # type: (IRequest, ISimpleAccountBinding) -> Deferred
    """
    Log out.
    """
    yield binding.unbindThisSession()
    returnValue(Redirect(b"/"))



@requirer.require(
    style.render, account=Authorization.optional(ISimpleAccount)
)
def ifLoggedIn(request, tag, account):
    # type: (IRequest, Tag, ISimpleAccount) -> Any
    """
    Render the given tag if the user is logged in, otherwise don't.
    """
    if account is None:
        return u""
    else:
        return tag



@requirer.require(style.render, account=Authorization.optional(ISimpleAccount))
def ifLoggedOut(request, tag, account):
    # type: (IRequest, Tag, ISimpleAccount) -> Any
    """
    Render the given tag if the user is logged in, otherwise don't.
    """
    if account is not None:
        return u""
    else:
        return tag


@requirer.require(
    style.render, form=Form.rendererFor(bye, "/logout")
)
def logoutGlue(request, tag, form):
    # type: (IRequest, Tag, RenderableForm) -> Tag
    return tag(form.glue())

@requirer.require(style.render, account=Authorization(ISimpleAccount))
def username(request, tag, account):
    # type: (IRequest, Tag, ISimpleAccount) -> Tag
    return tag(account.username)


@requirer.require(
    style.routed(app.route("/login", methods=["POST"]),
                 [tags.h1("u log in 2 ", slot("newAccountID"))]),
    binding=Authorization(ISimpleAccountBinding),
    username=Field.text(),
    password=Field.password(),
)
@inlineCallbacks
def dologin(request, username, password, binding):
    # type: (IRequest, str, str, ISimpleAccountBinding) -> Deferred
    account = yield binding.bindIfCredentialsMatch(username, password)
    if account is None:
        an_id = 'naaaahtthiiiing'
    else:
        an_id = account.accountID
    returnValue({
        "loginActive": "active",
        "newAccountID": an_id,
    })


@requirer.require(style.routed(
    app.route("/login", methods=["GET"]),
    [tags.h1("Log In....."),
     tags.div(Class="container")
     (tags.form(
         style="margin: auto; width: 400px; margin-top: 100px",
         action="/login",
         method="POST")
      (slot("glue_here"),
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
         ("Log In")))))]),
                  login_form=Form.rendererFor(dologin, action="/login")
)
def loginform(request, login_form):
    # type: (IRequest, RenderableForm) -> Dict
    return {
        "loginActive": "active",
        "glue_here": login_form.glue()
    }



@requirer.require(
    app.route("/sessions/logout", methods=["POST"]),
    binding=Authorization(ISimpleAccountBinding),
    sessionID=Field.text(),
)
@inlineCallbacks
def logOtherOut(request, sessionID, binding):
    # type: (IRequest, str, ISimpleAccountBinding) -> Deferred
    from attr import assoc
    # TODO: public API for getting to this?
    session = yield binding._session._sessionStore.loadSession(
        sessionID, request.isSecure(), SessionMechanism.Header
    )
    other_binding = assoc(binding, _session=session)
    yield other_binding.unbindThisSession()
    returnValue(Redirect(b"/sessions"))



widget = Plating(
    tags=tags.tr(style=slot("highlight"))(
        tags.td(slot("id")), tags.td(slot("ip")),
        tags.td(slot("when")),
        tags.td(tags.form(action="/sessions/logout",
                          method="POST")
                (tags.button("logout"),
                 tags.input(type="hidden", value=[slot("id")],
                            name="sessionID"),
                 slot("glue")))
    ),
    presentation_slots=["glue", "highlight"]
)

@widget.widgeted
def oneSession(session_info, form, current):
    # type: (Any, RenderableForm, bool) -> Dict
    # session_info is the private 'SessionIPInformation'
    return dict(
        id=session_info.id,
        ip=session_info.ip,
        when=(u"{:%a, %d %b %Y %H:%M:%S +0000}".format(session_info.when)),
        glue=form.glue(),
        highlight="background-color: rgb(200, 200, 255)" if current else ""
    )



@requirer.require(
    style.routed(
        app.route("/sessions", methods=["GET"]),
        [tags.h1("List of Sessions"),
         tags.table(border="5", cellpadding="2", cellspacing="2")
         (tags.transparent(render="sessions:list")
          (slot("item")))]
    ),
    form=Form.rendererFor(logOtherOut, action="/sessions/logout"),
    binding=Authorization.optional(ISimpleAccountBinding),
    session=Authorization(ISession),
)
@inlineCallbacks
def sessions(request, binding, form, session):
    # type: (IRequest, ISimpleAccountBinding, Form) -> Deferred
    if binding is None:
        returnValue({"sessions": []})
    else:
        dump = {
            "sessions": [
                oneSession.widget(
                    session_info, form, session.identifier == session_info.id
                )
                for session_info in (yield binding.boundSessionInformation())
            ]
        }
        returnValue(dump)



@requirer.require(
    style.routed(
        app.route("/signup", methods=["POST"]),
        [tags.h1(slot("success")),
         tags.p(
             "Now ", tags.a(href=slot("next_url"))(slot("link_message")), "."
         )]
    ),
    binding=Authorization(ISimpleAccountBinding),
    username=Field.text(),
    email=Field.text(),
    password=Field.password(),
)
@inlineCallbacks
def doSignup(request, username, email, password, binding):
    # type: (IRequest, str, str, str, ISimpleAccountBinding) -> Deferred
    acct = yield binding.createAccount(username, email, password)
    result = {
        "signupActive": "active",
        "accountID": None
    }
    if acct is None:
        result.update({
            "success": "Account creation failed!",
            "link_message": "try again",
            "next_url": "/signup",
        })
    else:
        result.update({
            "accountID": acct.accountID,
            "success": "Account created!",
            "link_message": "log in",
            "next_url": "/login"
        })
    returnValue(result)




@requirer.require(style.routed(
    app.route("/signup", methods=["GET"]),
    [tags.h1("Sign Up"),
     tags.div(Class="container")
     (tags.form(
         style="margin: auto; width: 400px; margin-top: 100px",
         action="/signup",
         method="POST")
      (slot("glue_here"),
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
         ("Sign Up")))))]),
                  theForm=Form.rendererFor(doSignup, action="/signup")
)
def signupPage(request, theForm):
    # type: (IRequest, RenderableForm) -> Dict
    return {
        "glue_here": theForm.glue(),
        "signupActive": "active"
    }

if __name__ == '__main__':
    app.run("localhost", 8976)
