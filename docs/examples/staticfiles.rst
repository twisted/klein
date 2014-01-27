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