from klein import route, run


@route("/")
def home(request):
    return "Hello, world!"


run("localhost", 8080)
