==========================
Example -- Handling Errors
==========================

It may be desirable to have uniform error-handling code for many routes.  We
can do this with ``Klein.handle_errors``.

Below we have created a class that will translate ``NotFound`` exceptions into
a custom 404 response.

.. code-block:: python

    from klein import Klein
    
    class NotFound(Exception):
        pass


    class ItemStore(object):
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


The following curl commands can be used to test this behaviour::

    curl -v -L http://localhost:8080/droid/R2D2
    curl -v -L http://localhost:8080/droid/Janeway
    curl -v -L http://localhost:8080/bounty/things