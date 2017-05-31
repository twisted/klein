import sqlite3
from contextlib import closing
from os import path

from jinja2 import Environment, PackageLoader
from klein import Klein
from twisted.web.static import File


app = Klein()


@app.route("/")
def home(self, request):
    templates = Environment(loader=PackageLoader("templates", package_path=""))
    db_name = "books.db"

    with closing(sqlite3.connect(db_name)) as con:
        cursor = con.cursor()
        cursor.execute("SELECT * from books;")
        all_books = cursor.fetchall()
    template = templates.get_template("homepage.html")
    return template.render(books=all_books)


@app.route("/static/<filename>")
def static(self, request, filename):
    # TODO note about static files
    return File(path.join("static", filename))


if __name__ == "__main__":
    app.run("localhost", 8080)
