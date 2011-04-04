Klein
=====

Klein is a small experiment to see whether it is possible to reasonably add
Werkzeug's WSGI enhancements on top of Twisted's web services. Like all Python
experiments for SCIENCE!, it was concocted on Freenode's #python and #twisted
and just sounded too cool to not try out.

A Klein bottle is an example of a non-orientable surface, and a glass Klein
bottle looks like a twisted bottle or twisted flask. This, of course, made it
too good of a pun to pass up.

Example
-------

::

    from twisted.web import server
    from twisted.application import service, internet
    from klein.resource import KleinResource
    from klein.decorators import expose

    class ExampleResource(KleinResource):
        @expose('/')
        def home(self, request):
            return 'wooooo'

        @expose('/<int:id>')
        def id(self, request, id):
            return 'id is %d' % (id,)

    application = service.Application('Example')
    internet.TCPServer(8081, server.Site(ExampleResource())).setServiceParent(application)
