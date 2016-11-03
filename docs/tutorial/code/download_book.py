import functools

from klein import Klein
import treq
from twisted.enterprise import adbapi
from twisted.internet import task, reactor

app = Klein()
dbpool = adbapi.ConnectionPool("sqlite3", "books.db", check_same_thread=False)


def return_response(response, request):
    request.setHeader("content-type", "text/plain")
    return response.content()


def got_sql_results(book_url, request):
    if not book_url:
        request.setResponseCode(404)
        return
    dfd = treq.get(book_url[0][0])
    dfd.addCallback(return_response, request)
    return dfd


@app.route("/book/<key>")
def book(request, key):
    query = "SELECT href from books where book_id=?;"
    dfd = dbpool.runQuery(query, key)
    dfd.addCallback(got_sql_results, request)
    return dfd


if __name__ == "__main__":
    app.run("localhost", 8080)
