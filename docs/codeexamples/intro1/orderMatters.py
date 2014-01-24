from klein import Klein
app = Klein()

@app.route('/')
def pg_root(request):
    return 'I will never be called'

@app.route('/')
def pg_root2(request):
    return 'I will be returned'

app.run("localhost", 8080)