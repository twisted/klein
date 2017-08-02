===========================
Example -- Using ``twistd``
===========================

Another important integration point with Twisted is the `twistd application runner <https://twistedmatrix.com/documents/current/core/howto/tap.html>`_.
It provides rich logging support, daemonization, reactor selection, profiler integration, and many more useful features.

To provide access to these features (and others like HTTPS) klein provides the ``resource`` function which returns a valid :api:`twisted.web.resource.IResource <IResource>` for your application.

Here is our "Hello, World!" application again in a form that can be launched by ``twistd``::

    from klein import resource, route

    @route('/')
    def hello(request):
        return "Hello, world!"


To run the above application we can save it as ``helloworld.py`` and use the ``twistd web`` plugin::

    PYTHONPATH=. twistd -n web --class=helloworld.resource
