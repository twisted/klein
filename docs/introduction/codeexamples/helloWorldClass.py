from klein import Klein


app = Klein()


@app.route("/")
def home(request):
    return "Hello, world!"


app.run("localhost", 8080)
