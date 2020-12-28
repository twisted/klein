from hashlib import sha256
from random import Random
from struct import unpack

from twisted.web.template import slot, tags

from klein import Klein, Plating


# Cobble together a deterministic random function using a string as a seed.
def random_from_string(string):
    return Random(unpack("!I", sha256(string.encode("utf-8")).digest()[:4])[0])


app = Klein()

myStyle = Plating(
    tags=tags.html(
        tags.head(tags.title(slot("pageTitle"))),
        tags.body(
            tags.h1(slot("pageTitle"), Class="titleHeading"),
            tags.div(slot(Plating.CONTENT)),
        ),
    ),
    defaults={"pageTitle": "Places & Foods"},
)


@myStyle.routed(
    app.route("/"),
    tags.div(
        tags.h2("Sample Places:"),
        tags.ul(
            [
                tags.li(tags.a(href=["/places/", place])(place))
                for place in ["new york", "san francisco", "shanghai"]
            ]
        ),
        tags.h2("Sample Foods:"),
        tags.ul(
            [
                tags.li(tags.a(href=["/foods/", food])(food))
                for food in ["hamburgers", "cheeseburgers", "hot dogs"]
            ]
        ),
    ),
)
def root(request):
    return {}


@myStyle.routed(
    app.route("/foods/<food>"),
    tags.table(border="2", style="color: blue")(
        tags.tr(tags.td("Name:"), tags.td(slot("name"))),
        tags.tr(tags.td("Deliciousness:"), tags.td(slot("rating"), " stars")),
        tags.tr(tags.td("Carbs:"), tags.td(slot("carbohydrates"))),
    ),
)
def one_food(request, food):
    random = random_from_string(food)
    return {
        "name": food,
        "pageTitle": f"Food: {food}",
        "rating": random.randint(1, 5),
        "carbohydrates": random.randint(0, 100),
    }


@myStyle.routed(
    app.route("/places/<place>"),
    tags.div(style="color: green")(
        tags.h1("Place: ", slot("name")),
        tags.div(slot("latitude"), "° ", slot("longitude"), "°"),
        tags.div(
            tags.h2("Foods Found Here:"),
            tags.ul(
                tags.li(render="foods:list")(
                    tags.a(href=["/foods/", slot("item")])(slot("item"))
                )
            ),
        ),
    ),
)
def one_place(request, place):
    random = random_from_string(place)
    possible_foods = [
        "hamburgers",
        "cheeseburgers",
        "hot dogs",
        "pizza",
        "叉烧",
        "皮蛋",
        "foie gras",
    ]
    random.shuffle(possible_foods)
    return {
        "name": place,
        "pageTitle": f"Place: {place}",
        "latitude": random.uniform(-90, 90),
        "longitude": random.uniform(-180, 180),
        "foods": possible_foods[:3],
    }


app.run("localhost", 8080)
