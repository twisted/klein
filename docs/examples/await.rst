============================
Example -- Using Async/Await
============================

The previous example which used the Twisted 
:api:`twisted.internet.defer.Deferred <Deferred>` class
can be written to use the new ``async`` and ``await``
keywords that are available in Python 3.5+.

Here is the same Google proxy, using `treq <https://github.com/twisted/treq>`_ and ``async`` and ``await``.

.. code-block:: python

    import treq
    from klein import Klein
    app = Klein()

    @app.route('/', branch=True)
    async def google(request):
        response = await treq.get(b'https://www.google.com' + request.uri)
        content = await treq.content(response)
        return content

    app.run("localhost", 8080)
