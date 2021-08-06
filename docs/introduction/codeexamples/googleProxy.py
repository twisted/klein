import treq

from klein import Klein


app = Klein()


@app.route("/", branch=True)
def google(request):
    d = treq.get("https://www.google.com" + request.uri)
    d.addCallback(treq.content)
    return d


app.run("localhost", 8080)
