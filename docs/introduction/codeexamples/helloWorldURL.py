from klein import Klein
app = Klein()

from twisted.python.url import URL

@app.route(URL())
def home(request):
    return 'Hello, world!'

app.run("localhost", 8080)
