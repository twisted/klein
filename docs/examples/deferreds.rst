==========================
Example -- Using Deferreds
==========================

And of course, this is Twisted.
So there is a wealth of APIs that return a :api:`twisted.internet.defer.Deferred <Deferred>`.
A Deferred may also be returned from handler functions and their result will be used as the response body.

Here is a simple Google proxy.

.. code-block:: python

    from twisted.web.client import getPage
    from klein import run, route

    @route('/')
    def google(request):
        return getPage('https://www.google.com' + request.uri)


    run("localhost", 8080)