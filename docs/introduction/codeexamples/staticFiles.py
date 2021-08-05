from twisted.web.static import File

from klein import Klein


app = Klein()


@app.route("/", branch=True)
def pg_index(request):
    return File("./")


app.run("localhost", 8080)
