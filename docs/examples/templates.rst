======================================
Example -- Using Twisted.Web Templates
======================================

You can also make easy use of ``twisted.web.templates`` by returning anything that implements ``twisted.web.template.IRenderable`` such as ``twisted.web.template.Element`` in which case the template will be rendered and the result will be sent as the response body.

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