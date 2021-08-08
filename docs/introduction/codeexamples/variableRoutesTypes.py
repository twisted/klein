from klein import Klein


app = Klein()


@app.route("/<string:arg>")
def pg_string(request, arg):
    return f"String: {arg}!"


@app.route("/<float:arg>")
def pg_float(request, arg):
    return f"Float: {arg}!"


@app.route("/<int:arg>")
def pg_int(request, arg):
    return f"Int: {arg}!"


app.run("localhost", 8080)
