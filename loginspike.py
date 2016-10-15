
from __future__ import print_function, unicode_literals, absolute_import

from twisted.web.template import tags, slot
from twisted.internet.defer import inlineCallbacks, returnValue

from klein import Klein, Plating, form
from klein.interfaces import ISimpleAccountBinding, SessionMechanism

from klein.storage.sql import open_session_store

from twisted.web.util import Redirect

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
                    tags.transparent(render="if_logged_in")(
                        tags.li(Class=["nav-item ", slot("sessions_active")])(
                            tags.a("Sessions", Class="nav-link",
                                   href="/sessions")),
                        tags.li(Class="nav-item pull-xs-right")(
                            tags.form(render="logout_glue",
                                      action="/logout",
                                      method="POST")(
                                          tags.button("Logout", Class="btn"),
                                      )
                        ),
                        tags.li(Class="nav-item pull-xs-right",
                        )(
                            tags.span(Class="nav-link active",
                                      render="username")
                        ),
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
        "sessions_active": "",
    }
)


@style.routed(app.route("/"),
              tags.h1(slot('result')))
def root(request):
    return {
        "result": "hello world",
        "home_active": "active"
    }

from twisted.internet import reactor
getproc = open_session_store(reactor, "sqlite:///sessions.sqlite")
@getproc.addCallback
def set_procurer(opened_procurer):
    global procurer
    procurer = opened_procurer

from klein._session import requirer, Optional
authorized = requirer(lambda: procurer)

logout = form().authorized_using(authorized)



@authorized(logout.handler(app.route("/logout", methods=["POST"])),
            binding=ISimpleAccountBinding)
@inlineCallbacks
def bye(request, binding):
    """
    Log out.
    """
    yield binding.log_out()
    returnValue(Redirect(b"/"))



@authorized(style.render, binding=Optional(ISimpleAccountBinding))
@inlineCallbacks
def if_logged_in(request, tag, binding):
    """
    Render the given tag if the user is logged in, otherwise don't.
    """
    if binding is None:
        returnValue(u"")
    account = next(iter((yield binding.authenticated_accounts())), None)
    if account is None:
        returnValue(u"")
    else:
        returnValue(tag)



@logout.renderer(style.render, "/logout")
def logout_glue(request, tag, form):
    glue = form.glue()
    return tag(glue)

@authorized(style.render, binding=ISimpleAccountBinding)
@inlineCallbacks
def username(request, tag, binding):
    account = next(iter((yield binding.authenticated_accounts())), None)
    returnValue(tag(account.username))


login = form(
    username=form.text(),
    password=form.password(),
).authorized_using(authorized)



@style.routed(
    login.renderer(app.route("/login", methods=["GET"]), action="/login",
                   argument="login_form"),
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
         ("Log In")))))]
)
def loginform(request, login_form):
    return {
        "login_active": "active",
        "glue_here": login_form.glue()
    }



@authorized(
    style.routed(login.handler(app.route("/login", methods=["POST"])),
                 [tags.h1("u log in 2 ", slot("new_account_id"))]),
    binding=ISimpleAccountBinding,
)
@inlineCallbacks
def dologin(request, username, password, binding):
    account = yield binding.log_in(username, password)
    if account is None:
        an_id = 'naaaahtthiiiing'
    else:
        an_id = account.account_id
    returnValue({
        "login_active": "active",
        "new_account_id": an_id,
    })



logout_other = form(
    session_id=form.text(),
).authorized_using(authorized)

@authorized(
    logout_other.handler(app.route("/sessions/logout", methods=["POST"])),
    binding=ISimpleAccountBinding,
)
@inlineCallbacks
def log_other_out(request, session_id, binding):
    from attr import assoc
    session = yield binding._session._session_store.load_session(
        session_id, request.isSecure(),
        SessionMechanism.Header
    )
    other_binding = assoc(binding, _session=session)
    yield other_binding.log_out()
    returnValue(Redirect(b"/sessions"))



@Plating.widget(
    tags=tags.tr(style=slot("highlight"))(
        tags.td(slot("id")), tags.td(slot("ip")),
        tags.td(slot("when")),
        tags.td(tags.form(action="/sessions/logout",
                          method="POST")
                (tags.button("logout"),
                 tags.input(type="hidden", value=[slot("id")],
                            name="session_id"),
                 slot("glue")))
    ),
    presentation_slots=["glue", "highlight"]
)
def one_session(session_info, form, current):
    return dict(
        id=session_info.id,
        ip=session_info.ip,
        when=(session_info.when
              .strftime("%a, %d %b %Y %H:%M:%S +0000")
              .decode("utf-8")),
        glue=form.glue(),
        highlight="background-color: rgb(200, 200, 255)" if current else ""
    )



@authorized(
    logout_other.renderer(
        style.routed(app.route("/sessions", methods=["GET"]),
                     [tags.h1("List of Sessions"),
                      tags.table(border="5",
                                 cellpadding="2", cellspacing="2"
                      )(tags.transparent(render="sessions:list")
                        (slot("item")))]),
        "/sessions/logout",
    ),
    # If all bindings are Optional, then session creation should be optional.
    binding=Optional(ISimpleAccountBinding),
)
@inlineCallbacks
def sessions(request, binding, form):
    from klein.interfaces import ISession
    if binding is None:
        returnValue({"sessions": []})
    dump = {
        "sessions": [one_session.widget(
            session_info, form, ISession(request).identifier == session_info.id
        )
                     for session_info in (yield binding.attached_sessions())]
    }
    returnValue(dump)



signup = form(
    username=form.text(),
    email=form.text(),
    password=form.password(),
).authorized_using(authorized)

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
         ("Sign Up")))))]
)
def signup_page(request, the_form):
    return {
        "glue_here": the_form.glue(),
        "signup_active": "active"
    }



@authorized(
    style.routed(
        signup.handler(app.route("/signup", methods=["POST"])),
        [tags.h1(slot("success")),
         tags.p(
             "Now ", tags.a(href=slot("next_url"))(slot("link_message")), "."
         )]
    ),
    binding=ISimpleAccountBinding
)
@inlineCallbacks
def do_signup(request, username, email, password, binding):
    acct = yield binding.create_account(username, email, password)
    result = {
        "signup_active": "active",
        "account_id": None
    }
    if acct is None:
        result.update({
            "success": "Account creation failed!",
            "link_message": "try again",
            "next_url": "/signup",
        })
    else:
        result.update({
            "account_id": acct.account_id,
            "success": "Account created!",
            "link_message": "log in",
            "next_url": "/login"
        })
    returnValue(result)



if __name__ == '__main__':
    app.run("localhost", 8976)
