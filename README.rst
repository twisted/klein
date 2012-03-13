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

    from klein import run, route

    @route('/')
    def home(request):
        return 'wooooo'

    @route('/<int:id>')
    def id(self, request, id):
        return 'id is %d' % (id,)

    run("localhost", 8080)