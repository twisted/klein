==========================
Example -- Using Deferreds
==========================

And of course, this is Twisted.
So there is a wealth of APIs that return a :api:`twisted.internet.defer.Deferred <Deferred>`.
A Deferred may also be returned from handler functions and their result will be used as the response body.

Here is a simple Google proxy, using `treq <https://github.com/twisted/treq>`_ (think Requests, but using Twisted)::

    import treq
    from klein import Klein
    app = Klein()

    @app.route('/', branch=True)
    def google(request):
        d = treq.get(b'https://www.google.com' + request.uri)
        d.addCallback(treq.content)
        return d

    app.run("localhost", 8080)
