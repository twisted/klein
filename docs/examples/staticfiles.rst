===============================
Example -- Serving Static Files
===============================

Helpfully you can also return a :api:`twisted.web.resource.IResource <t.w.resource.IResource>` such as :api:`twisted.web.static.File <t.w.static.File>`.
If ``branch=True`` is passed to ``route`` the returned ``IResource`` will also be allowed to handle all children path segments.
So ``http://localhost:8080/static/img.gif`` should return an image and ``http://localhost:8080/static/`` should return a directory listing.

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

In production environments, you might want to disable directory listings so
that you do not accidentally expose more information than you intend. To
disable directory listings, override the ``directoryListing`` method for the
:api:`twisted.web.static.File <t.w.static.File>` class.

.. code-block:: python

    from twisted.web.static import File
    from klein import run, route
    from werkzeug.exceptions import NotFound

    @route('/static/', branch=True)
    def static(request):
        return FileNoDir("./static")

    @route('/')
    def home(request):
        return '<img src="/static/img.gif">'

    class FileNoDir(File):
        def directoryListing(self):
            raise NotFound()

    run("localhost", 8080)
