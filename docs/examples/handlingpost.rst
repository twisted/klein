========================
Example -- Handling POST
========================

The ``route`` decorator supports a ``methods`` keyword which is the list of HTTP methods as strings.
For example, ``methods=['POST']`` will cause the handler to be invoked when an ``POST`` request is received.
If a handler can support multiple methods the current method can be distinguished with ``request.method``.

Here is our ``"Hello, world!"`` example extended to support setting the name we are saying Hello to via a ``POST`` request with a ``name`` argument.

This also demonstrates the use of the redirect method of the request to redirect back to ``'/'`` after handling the ``POST``.

The most specific handler should be defined first.
So the ``POST`` handler must be defined before the handler with no ``methods``.

.. code-block:: python

    from twisted.internet.defer import succeed
    from klein import run, route

    name = b"world"

    @route("/", methods=["POST"])
    def setname(request):
        global name
        name = request.args.get(b'name', [b'world'])[0]
        request.redirect('/')
        return succeed(None)

    @route('/')
    def hello(request):
        return b"Hello, %s!" % (name,)

    run("localhost", 8080)


The following curl command can be used to test this behaviour::

    curl -v -L -d name='bob' http://localhost:8080/


Accessing the request content
=============================

To read the content of the request use the ``read`` method of
:api:`twisted.web.iweb.IRequest <IRequest.content>`

.. code-block:: python

    from klein import run, route
    import json

    @route('/', methods=['POST'])
    def do_post(request):
        content = json.loads(request.content.read())
        response = json.dumps(dict(the_data=content), indent=4)
        return response

    run("localhost", 8080)


The following curl command can be used to test this behaviour::

     curl -XPOST -v -H 'Content-Type: appliction/json' -d '{"name":"bob"}'  http://localhost:8080/
