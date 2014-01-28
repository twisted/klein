======================================
Example -- Using Twisted.Web Templates
======================================

You can also make easy use of :api:`twisted.web.template <Twisted's templating system>` by returning anything that implements :api:`twisted.web.iweb.IRenderable <IRenderable>`.
For example, returning a :api:`twisted.web.template.Element <t.w.template.Element>` will make it be rendered, with the result sent as the response body::

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
