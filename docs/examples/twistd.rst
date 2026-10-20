===========================
Example -- Using ``twistd``
===========================

Another important integration point with Twisted is the `twistd application runner <https://docs.twisted.org/en/stable/core/howto/tap.html>`_.
It provides rich logging support, daemonization, reactor selection, profiler integration, and many more useful features.

To provide access to these features (and others like HTTPS) klein provides the ``resource`` function which returns a valid :api:`twisted.web.resource.IResource <IResource>` for your application.

Here is our "Hello, World!" application again in a form that can be launched by ``twistd``::

    from klein import resource, route

    @route('/')
    def hello(request):
        return "Hello, world!"


To run the above application we can save it as ``helloworld.py`` and use the ``twistd web`` plugin::

    PYTHONPATH=. twistd -n web --class=helloworld.resource


Adding Klein to an Application
==============================

To combine Klein with other Twisted services, wrap ``app.resource()`` in a :api:`twisted.web.server.Site <Site>` and pass that factory to :api:`twisted.application.internet.TCPServer <TCPServer>`.
The resulting service can be attached to your existing ``Application`` or ``MultiService`` with ``setServiceParent``.
Klein provides the HTTP resource; the parent service manages when the listener starts and stops.

Here is a complete application, saved as ``service.tac``:

.. literalinclude:: service.tac
   :language: python

Run it in the foreground:

.. code-block:: shell

    twistd -n -y service.tac

Visit ``http://127.0.0.1:8080/`` to see ``Hello, world!``.
Press Ctrl-C to stop the application and its listener.
The example binds only to the loopback interface and disables traceback pages.

When adding this to an existing application, use its parent service instead of creating another ``Application``.
Do not call ``app.run()`` or ``reactor.run()`` in the ``.tac`` file: ``twistd`` runs the reactor and starts and stops the attached services.
See Twisted's `Application framework guide <https://docs.twisted.org/en/stable/core/howto/application.html>`_ for more about composing services.
