from klein import Klein
from twisted.application import internet, service
from twisted.web.server import Site

app = Klein()


@app.route("/")
def hello(request):
    return "Hello, world!"


site = Site(app.resource())
site.displayTracebacks = False
http_service = internet.TCPServer(8080, site, interface="127.0.0.1")
application = service.Application("klein-example")
http_service.setServiceParent(application)
