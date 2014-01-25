from klein import Klein
app = Klein()

@app.route('/user/<username>')
def pg_user(request, username):
    return 'Hi %s!' % (username,)

@app.route('/user/bob')
def pg_user_bob(request):
    return 'Hello there bob!'

app.run("localhost", 8080)
