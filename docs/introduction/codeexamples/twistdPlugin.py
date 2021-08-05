from klein import Klein


app = Klein()


@app.route("/")
def hello(request):
    return "Hello, world!"


resource = app.resource
