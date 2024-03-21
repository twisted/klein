from twisted.web.template import Tag, slot, tags

from klein import Plating


page = Plating(
    tags=tags.html(
        tags.head(
            tags.title("Food Ratings Example: ", slot("pageTitle")),
            slot("headExtras"),
            tags.style(
                """
            .nav a {
                padding-left: 2em;
            }
            form {
                border: 1px solid grey;
                border-radius: 1em;
                padding: 1em;
            }
            form label {
                display: block;
                padding: 0.2em;
            }
            """
            ),
        ),
        tags.body(
            tags.div(class_="nav")(
                "navigation:",
                tags.a(href="/")("home"),
                tags.a(href="/login", render="whenLoggedOut")("login"),
                tags.a(href="/signup", render="whenLoggedOut")("signup"),
                tags.a(href="/api-keys", render="whenLoggedIn")(
                    "API Key Management"
                ),
                tags.a(href="/logout", render="whenLoggedIn")("logout"),
            ),
            tags.h1("Food Ratings Example: ", slot("pageTitle")),
            tags.div(slot(Plating.CONTENT)),
        ),
    ),
    defaults={"pageTitle": "", "headExtras": ""},
    presentation_slots=["pageTitle", "headExtras"],
)


@page.fragment
def food(name: str, rating: str) -> Tag:
    return tags.div(
        tags.div("food:", name),
        tags.div("rating:", rating),
    )


@page.fragment
def linkedFood(name: str, rating: str, username: str) -> Tag:
    return tags.div(
        tags.div("food:", name),
        tags.div("rating:", rating),
        tags.div("user:", tags.a(href=["/users/", username])(username)),
    )


def refresh(url: str) -> Tag:
    return tags.meta(content=f"0;URL='{url}'", **{"http-equiv": "refresh"})
