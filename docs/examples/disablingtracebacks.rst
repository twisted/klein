====================================
Example -- Disabling traceback pages
====================================

If processing a request fails, by default Klein (and Twisted) show an error
page that prints the traceback and other useful debugging information.

This is not desirable when you deploy code publicly, in such a case, you
should disable this behaviour.

There are multiple ways to do this, you can do this on a Klein-app scope or
change the default for the python process.

We will use following Klein app:

.. code-block:: python

    from klein import Klein

    app = Klein()

    @app.route('/OK')
    def requestOK(self, request):
        return 'OK'

    @app.route('/KO')
    def requestKO(self, request):
        raise RuntimeError('Oops')


Example - Disable traceback pages on a single Klein app
=======================================================

This works by passing the ``displayTracebacks`` argument as ``False``
to ``app.run``.

.. code-block:: python

    if __name__ == '__main__':
        import sys
        displayTracebacks = '--production' not in sys.args

        # The Klein app will not display tracebacks if the script is called
        # with a --production argument, but it will otherwise.
        app.run('localhost', 8080, displayTracebacks=displayTracebacks)


Example - Disable traceback pages process wide
==============================================

This method also affects other Twisted Sites.

Under the hood, Klein uses ``twisted.web.server.Site``, which has an
instance variable ``displayTracebacks`` that defaults to ``True``.

For the rationale behind that, check
https://twistedmatrix.com/trac/ticket/135

.. code-block:: python

    # Disable tracebacks by default for any Site object.
    from twisted.web.server import Site
    Site.displayTracebacks = False


    if __name__ == '__main__':
        # The Klein app won't display tracebacks
        app.run('localhost', 8080)
