from klein import Klein
app = Klein()

@app.route('/user/<username>')
def pg_user(request, username):
    return 'Hi %s!' % (username,)

app.run("localhost", 8080)