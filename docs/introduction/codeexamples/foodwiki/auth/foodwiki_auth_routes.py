from foodwiki_config import app, requirer
from foodwiki_db import APIKeyProvisioner
from foodwiki_templates import page, refresh

from twisted.web.template import slot, tags

from klein import Authorization, Field, Form, RenderableForm
from klein.interfaces import ISimpleAccountBinding


@requirer.require(
    page.routed(
        app.route("/signup", methods=["POST"]),
        tags.h1("signed up", slot("signedUp")),
    ),
    username=Field.text(),
    password=Field.password(),
    password2=Field.password(),
    binding=Authorization(ISimpleAccountBinding),
)
async def signup(
    username: str, password: str, password2: str, binding: ISimpleAccountBinding
) -> dict:
    await binding.createAccount(username, "", password)
    return {"signedUp": "yep", "headExtras": refresh("/login")}


@requirer.require(
    page.routed(
        app.route("/signup", methods=["GET"]),
        tags.div(tags.h1("sign up pls"), slot("signupForm")),
    ),
    binding=Authorization(ISimpleAccountBinding),
    theForm=Form.rendererFor(signup, action="/signup"),
)
async def showSignup(
    binding: ISimpleAccountBinding,
    theForm: RenderableForm,
) -> dict:
    return {"signupForm": theForm}


@requirer.require(
    page.routed(
        app.route("/login", methods=["POST"]),
        tags.div(tags.h1("logged in", slot("didlogin"))),
    ),
    username=Field.text(),
    password=Field.password(),
    binding=Authorization(ISimpleAccountBinding),
)
async def login(
    username: str, password: str, binding: ISimpleAccountBinding
) -> dict:
    didLogIn = await binding.bindIfCredentialsMatch(username, password)
    if didLogIn is not None:
        return {
            "didlogin": "yes",
            "headExtras": refresh("/"),
        }
    else:
        return {
            "didlogin": "no",
            "headExtras": refresh("/login"),
        }


@requirer.require(
    page.routed(app.route("/login", methods=["GET"]), slot("loginForm")),
    loginForm=Form.rendererFor(login, action="/login"),
)
def loginForm(loginForm: RenderableForm) -> dict:
    return {"loginForm": loginForm}


@requirer.require(
    page.routed(
        app.route("/logout", methods=["POST"]),
        tags.div(tags.h1("logged out ", slot("didlogout"))),
    ),
    binding=Authorization(ISimpleAccountBinding),
    ignored=Field.submit("log out"),
)
async def logout(
    binding: ISimpleAccountBinding,
    ignored: str,
) -> dict:
    await binding.unbindThisSession()
    return {"didlogout": "yes", "headExtras": refresh("/")}


@requirer.require(
    page.routed(
        app.route("/logout", methods=["GET"]),
        tags.div(slot("button")),
    ),
    form=Form.rendererFor(logout, action="/logout"),
)
async def logoutView(form: RenderableForm) -> dict:
    return {
        "pageTitle": "log out?",
        "button": form,
    }


@requirer.require(
    page.routed(
        app.route("/new-api-key"),
        [
            tags.div("API Key Created"),
            tags.div("Copy this key; when you close this window, it's gone:"),
            tags.div(tags.code(slot("key"))),
            tags.div(tags.a(href="/api-keys")("back to API key management")),
        ],
    ),
    ok=Field.submit("New API Key"),
    provisioner=Authorization(APIKeyProvisioner),
)
async def createAPIKey(ok: object, provisioner: APIKeyProvisioner) -> dict:
    return {"key": await provisioner.provisionAPIKey()}


@requirer.require(
    page.routed(
        app.route("/api-keys", methods=["GET"]),
        tags.div(tags.h1("API Key Management"), slot("form")),
    ),
    form=Form.rendererFor(createAPIKey, action="/new-api-key"),
)
async def listAPIKeys(form: RenderableForm) -> dict:
    return {"form": form}
