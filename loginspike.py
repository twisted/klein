
from __future__ import print_function, unicode_literals, absolute_import

from twisted.web.template import tags, slot

from klein import Klein, Plating

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

@style.routed(
    app.route("/signup"),
    [tags.h1("Sign Up"),
     tags.div(Class="container")
     (tags.form(
         style="margin: auto; width: 400px;"
         "margin-top: 100px")
      (tags.div(Class="form-group row")
       (tags.label(For="anEmail",
                        Class="col-sm-3 col-form-label")("Email: "),
        tags.div(Class="col-sm-8")(
            tags.input(type="email", Class="form-control",
                       autofocus="true",
                       id="anEmail", placeholder="Email")
        )),
       tags.div(Class="form-group row")
       (tags.label(For="anPassword",
                        Class="col-sm-3 col-form-label")("Password: "),
        tags.div(Class="col-sm-8")(
            tags.input(type="password", Class="form-control",
                       id="anPassword", placeholder=""))),
       tags.div(Class="form-group row")
       (tags.div(Class="offset-sm-2 col-sm-8")
        (tags.button(type="submit", Class="btn btn-primary")
         ("Log In")))
      ))]
)
def signupform(request):
    """
    
    """
    return {}


app.run("localhost", 8976)
