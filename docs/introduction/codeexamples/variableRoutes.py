from klein import Klein


app = Klein()


@app.route("/user/<username>")
def pg_user(request, username):
    return f"Hi {username}!"


app.run("localhost", 8080)
