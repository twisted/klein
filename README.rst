Klein
=====

.. image:: https://secure.travis-ci.org/dreid/klein.png?branch=master

Klein is a micro-framework for developing production ready web services with
python.  It is 'micro' in that it has an incredibly small API similar to bottle
and flask.  It is not 'micro' in that it depends on things outside the standard
library.  This is primarily because it is built on widely used and well tested
components like werkzeug and Twisted.

A Klein bottle is an example of a non-orientable surface, and a glass Klein
bottle looks like a twisted bottle or twisted flask. This, of course, made it
too good of a pun to pass up.

Examples
-------

Here are some basic klein handler functions that return some strings.

::

    from klein import run, route

    @route('/')
    def home(request):
        return 'Hello, world!'

    run("localhost", 8080)


Static files
~~~~~~~~~~~~

Helpfully you can also return a ``twisted.web.resource.IResource`` such as
``static.File``.  If the URL passed to ``route`` ends in a ``/`` then the
returned ``IResource`` will also be allowed to handle all children path
segments.  So ``http://localhost:8080/static/img.gif`` should return an
image and ``http://localhost:8080/static/`` should return a directory
listing.

::

    from twisted.web.static import File
    from klein import run, route

    @route('/static/')
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

::

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
``twisted.internet.defer.Deferred``.  ``Deferred``s may also be returned from
handler functions and their result will be used as the response body.

Here is a simple Google proxy.

::

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

::

    from klein import resource, route

    @route('/')
    def hello(request):
        return "Hello, world!"


To run the above application we can save it as ``helloworld.py`` and use the
``twistd web`` plugin.

::

    twistd -n web --class=helloworld.resource
