==========================
Example -- Handling Errors
==========================

It may be desirable to have uniform error-handling code for many routes.
We can do this with ``Klein.handle_errors``.

Below we have created a class that will translate ``NotFound`` exceptions into a custom 404 response.

.. code-block:: python

    from klein import Klein

    class NotFound(Exception):
        pass


    class ItemStore:
        app = Klein()

        @app.handle_errors(NotFound)
        def notfound(self, request, failure):
            request.setResponseCode(404)
            return 'Not found, I say'

        @app.route('/droid/<string:name>')
        def droid(self, request, name):
            if name in ['R2D2', 'C3P0']:
                raise NotFound()
            return 'Droid found'

        @app.route('/bounty/<string:target>')
        def bounty(self, request, target):
            if target == 'Han Solo':
                return '150,000'
            raise NotFound()


    if __name__ == '__main__':
        store = ItemStore()
        store.app.run('localhost', 8080)


The following cURL commands (and output) can be used to test this behaviour::

    curl -L http://localhost:8080/droid/R2D2
    Not found, I say

    curl -L http://localhost:8080/droid/Janeway
    Droid found

    curl -L http://localhost:8080/bounty/things
    Not found, I say


Example - Catch All Routes
==========================

A simple way to create a catch-all function, which serves every URL that doesn't match a route, is to use a ``path`` variable in the route.

.. code-block:: python

    from klein import Klein

    class OnlyOneRoute:
        app = Klein()

        @app.route('/api/<path:catchall>')
        def catchAll(self, request, catchall):
            request.redirect('/api')

        @app.route('/api')
        def home(self, request):
            return 'API Home'

        @app.route('/api/v1')
        def v1(self, request):
            return 'Version 1 - Home'


    if __name__ == '__main__':
        oneroute = OnlyOneRoute()
        oneroute.app.run('localhost', 8080)


Use cURL to verify that only ``/api`` and ``/api/v1`` return content, all other requests are redirected::

   curl -L http://localhost:8080/api
   API Home

   curl -L localhost:8080/api/v1
   Version 1 - Home

   curl -L localhost:8080/api/another
   API Home


This method can also be used on the root route, in which case it will catch every request which doesn't match a route.
