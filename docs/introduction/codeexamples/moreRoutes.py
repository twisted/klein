from klein import Klein


app = Klein()


@app.route("/")
def pg_root(request):
    return "I am the root page!"


@app.route("/about")
def pg_about(request):
    return "I am a Klein application!"


app.run("localhost", 8080)
