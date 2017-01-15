from klein import Klein
from twisted.python.url import URL

app = Klein()

@app.route(URL(path=('user', '<username>')))
def pg_user(request, username):
    return 'Hi %s!' % (username,)

app.run("localhost", 8080)
