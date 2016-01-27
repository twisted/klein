from klein import Klein
app = Klein()

@app.route('/user/<username>')
def pg_user(request, username):
    return 'Hi {0}!'.format(username)

app.run("localhost", 8080)
