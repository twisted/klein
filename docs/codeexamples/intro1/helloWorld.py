from klein import run, route

@route('/')
def home(request):
    return 'Hello, world!'

run("localhost", 8080)
