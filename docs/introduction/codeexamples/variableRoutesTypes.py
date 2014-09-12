from klein import Klein
app = Klein()

@app.route('/<string:arg>')
def pg_string(request, arg):
    return 'String: %s!' % (arg,)

@app.route('/<float:arg>')
def pg_float(request, arg):
    return 'Float: %s!' % (arg,)

@app.route('/<int:arg>')
def pg_int(request, arg):
    return 'Int: %s!' % (arg,)

app.run("localhost", 8080)
