Klein
=====

.. image:: https://travis-ci.org/twisted/klein.png?branch=master
    :target: http://travis-ci.org/twisted/klein
    :alt: Build Status

Klein is a micro-framework for developing production ready web services with
python.  It is 'micro' in that it has an incredibly small API similar to bottle
and flask.  It is not 'micro' in that it depends on things outside the standard
library.  This is primarily because it is built on widely used and well tested
components like werkzeug and Twisted.

A Klein bottle is an example of a non-orientable surface, and a glass Klein
bottle looks like a twisted bottle or twisted flask. This, of course, made it
too good of a pun to pass up.

Examples
--------

Here are some basic klein handler functions that return some strings.

.. code-block:: python

    from klein import run, route

    @route('/')
    def home(request):
        return 'Hello, world!'

    run("localhost", 8080)


Static files
~~~~~~~~~~~~

Helpfully you can also return a ``twisted.web.resource.IResource`` such as
``static.File``.  If the ``branch=True`` is passed to ``route`` the
returned ``IResource`` will also be allowed to handle all children path
segments.  So ``http://localhost:8080/static/img.gif`` should return an
image and ``http://localhost:8080/static/`` should return a directory
listing.

.. code-block:: python

    from twisted.web.static import File
    from klein import run, route

    @route('/static/', branch=True)
    def static(request):
        return File("./static")

    @route('/')
    def home(request):
        return '<img src="/static/img.gif">'

    run("localhost", 8080)


Templates
~~~~~~~~~

You can also make easy use of ``twisted.web.templates`` by returning anything
that implements ``twisted.web.template.IRenderable`` such as
``twisted.web.template.Element`` in which case the template will be rendered
and the result will be sent as the response body.

.. code-block:: python

    from twisted.web.template import Element, XMLString, renderer
    from klein import run, route

    class HelloElement(Element):
        loader = XMLString((
            '<h1 '
            'xmlns:t="http://twistedmatrix.com/ns/twisted.web.template/0.1"'
            '>Hello, <span t:render="name"></span>!</h1>'))

        def __init__(self, name):
            self._name = name

        @renderer
        def name(self, request, tag):
            return self._name


    @route('/hello/<string:name>')
    def home(request, name='world'):
        return HelloElement(name)

    run("localhost", 8080)


Deferreds
~~~~~~~~~

And of course, this is twisted.  So there is a wealth of APIs that return a
``twisted.internet.defer.Deferred``.  A ``Deferred`` may also be returned from
handler functions and their result will be used as the response body.

Here is a simple Google proxy.

.. code-block:: python

    from twisted.web.client import getPage
    from klein import run, route

    @route('/')
    def google(request):
        return getPage('https://www.google.com' + request.uri)


    run("localhost", 8080)


twistd
~~~~~~

Another very important integration point with Twisted is the ``twistd``
application runner.  It provides rich logging support, daemonization, reactor
selection, profiler integration, and many more incredibly useful features.

To provide access to these features (and others like HTTPS) klein provides the
``resource`` function which returns a valid ``twisted.web.resource.IResource``
for your application.

Here is our "Hello, World!" application again in a form that can be launched
by ``twistd``.

.. code-block:: python

    from klein import resource, route

    @route('/')
    def hello(request):
        return "Hello, world!"


To run the above application we can save it as ``helloworld.py`` and use the
``twistd web`` plugin.

::

    twistd -n web --class=helloworld.resource


Handling POST
~~~~~~~~~~~~~

The ``route`` decorator supports a ``methods`` keyword which is the list of
HTTP methods as strings.  For example ``methods=['POST']`` will cause the
handler to be invoked when an ``POST`` request is received.  If a handler
can support multiple methods the current method can be distinguished with
``request.method``.

Here is our ``"Hello, world!"`` example extended to support setting the
name we are saying Hello to via a ``POST`` request with a ``name``
argument.

This also demonstrates the use of the redirect method of the request to
redirect back to ``'/'`` after handling the ``POST``.

The most specific handler should be defined first.  So the ``POST`` handler
must be defined before the handler with no ``methods``.

.. code-block:: python

    from twisted.internet.defer import succeed
    from klein import run, route

    name='world'

    @route('/', methods=['POST'])
    def setname(request):
        global name
        name = request.args.get('name', ['world'])[0]
        request.redirect('/')
        return succeed(None)

    @route('/')
    def hello(request):
        return "Hello, {0}!".format(name)

    run("localhost", 8080)


The following curl command can be used to test this behaviour::

    curl -v -L -d name='bob' http://localhost:8080/


Non-global state
~~~~~~~~~~~~~~~~

For obvious reasons it may be desirable for your application to have some
non-global state that is used by the your route handlers.

Below we have created a simple ``ItemStore`` class that has an instance of
``Klein`` as a class variable ``app``.  We can now use ``@app.route`` to
decorate the methods of the class.


.. code-block:: python

    import json

    from klein import Klein


    class ItemStore(object):
        app = Klein()

        def __init__(self):
            self._items = {}

        @app.route('/')
        def items(self, request):
            request.setHeader('Content-Type', 'application/json')
            return json.dumps(self._items)

        @app.route('/<string:name>', methods=['PUT'])
        def save_item(self, request, name):
            request.setHeader('Content-Type', 'application/json')
            body = json.loads(request.content.read())
            self._items[name] = body
            return json.dumps({'success': True})

        @app.route('/<string:name>', methods=['GET'])
        def get_item(self, request, name):
            request.setHeader('Content-Type', 'application/json')
            return json.dumps(self._items.get(name))


    if __name__ == '__main__':
        store = ItemStore()
        store.app.run('localhost', 8080)
