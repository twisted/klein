from twisted.web.template import tags, slot
from klein import Klein, Plating
app = Klein()

style = Plating(
    tags=tags.html(
        tags.head(tags.title(slot("title"))),
        tags.body(tags.h1(slot("title"), Class="title"),
                  tags.div(slot(Plating.CONTENT)))
    )
)

@style.routed(app.route("/"),
              (tags.div(slot("kind"), Class="label"),
               tags.ul(tags.li(slot("item"),
                               render="numbers:list"))))
def root(request):
    return {
        "title": "My Favorite Numbers",
        "kind": "Primes",
        "numbers": [1, 3, 5, 7, 9],
    }

@style.routed(app.route("/about"),
              tags.p(slot("about-text")))
def about(request):
    return {"about-text": "This is the 'about' page."}

app.run("localhost", 8080)
