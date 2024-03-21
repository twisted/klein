from twisted.web.template import Tag, slot, tags

from klein import Plating


page = Plating(
    tags=tags.html(
        tags.head(
            tags.title("Food Ratings Example: ", slot("pageTitle")),
            slot("headExtras"),
        ),
        tags.body(
            tags.h1("Food Ratings Example: ", slot("pageTitle")),
            tags.div(slot(Plating.CONTENT)),
        ),
    ),
    defaults={"pageTitle": "", "headExtras": ""},
)


@page.fragment
def food(name: str, rating: str) -> Tag:
    return tags.div(
        tags.div("food:", name),
        tags.div("rating:", rating),
    )


def refresh(url: str) -> Tag:
    return tags.meta(content=f"0;URL='{url}'", **{"http-equiv": "refresh"})
