from functools import wraps

from twisted.internet import reactor
from twisted.web.server import Site

from klein.decorators import expose
from klein.resource import KleinResource

routes = {}

def route(r):
    def deco(f):
        # Swallow self.
        # XXX hilariously, staticmethod would be *great* here.
        @wraps(f)
        def inner(self, *args, **kwargs):
            return f(*args, **kwargs)
        routes[f.__name__] = expose(r)(inner)
    return deco

def run(host=None, port=8080):
    # Invoke the metaclass directly.
    runner = KleinResource.__metaclass__("runner", (KleinResource,), routes)
    site = Site(runner())
    reactor.listenTCP(port, site, interface=host)
    reactor.run()
