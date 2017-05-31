from jinja2 import Environment, PackageLoader
from klein import Klein
from twisted.enterprise import adbapi

app = Klein()
dbpool = adbapi.ConnectionPool("sqlite3", "books.db", check_same_thread=False)


@app.route("/")
def home(request):
    templates = Environment(loader=PackageLoader("templates", package_path=""))

    def got_sql_results(all_books):
        template = templates.get_template("homepage.html")
        return template.render(books=all_books)

    dfd = dbpool.runQuery("SELECT * from books;")
    dfd.addCallback(got_sql_results)
    return dfd

if __name__ == "__main__":
    app.run("localhost", 8080)
