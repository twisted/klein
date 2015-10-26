===============================
Introduction -- Getting Started
===============================

Klein is a micro-framework for developing production-ready web services with Python.
It does this by building on top of Werkzeug and Twisted to combine their strengths.
This introduction is meant as a general introduction to Klein concepts.
The purpose of this introduction is to show you how to use install, test, and deploy web applications using Klein.
The examples in this introduction are all self-contained pieces of code.
Some of them are also tiny but independently runnable Klein apps.


Installing
==========

Klein is available on PyPI and can be installed with ``pip``::

    pip install klein

This is the canonical way to install Klein.

.. note::

   Klein is based on Twisted: ``pip`` will try to install Twisted for you, but you may need to install the non-Python packages that Twisted requires.
   To install these yourself, you will need the Python development headers and a compiler.
   On Debian-flavored Linux distributions such as Ubuntu or Mint, you can install them with this command::
     apt-get install python-dev build-essential

   On other Linux distributions you may need to instead install the appropriate packages via ``pacman`` or ``yum``.
   Twisted is available in the FreeBSD ports tree as ``devel/py-twisted``.
   A Windows installer is available from the `TwistedMatrix download page <http://twistedmatrix.com/trac/wiki/Downloads>`_, and OS X users may need to install XCode.


Hello World
===========

This example implements a web server that will respond to requests for ``/`` with "Hello, world!"

.. literalinclude:: codeexamples/helloWorld.py

This code defines one URL that the app responds to: ``/``.
It uses the ``@route`` decorator to tell Klein that the decorated function should be run to handle requests for ``/``.
After defining ``home()`` as a route, ``run()`` starts a Twisted Web server on port 8080 and listens for requests from localhost.

Because ``route`` and ``run`` were imported by themselves, they are associated with the default, global Klein instance.
This strategy is fine for very, very small applications.
However, to exercise more control, you'll need to make your own instance of Klein, as in this next example.

.. literalinclude:: codeexamples/helloWorldClass.py

.. note::
   Creating your own instance of ``klein.Klein`` like this is the recommended way to use Klein.
   Being explicit rather than implicit about the association between a route definition and a Klein instance or between a ``run()`` invocation and what it's running, allows more flexible and extensible use patterns.


Adding Routes
=============

Add more decorated functions to add more routes to your Klein applications.

.. literalinclude:: codeexamples/moreRoutes.py


Variable Routes
===============

You can also make `variable routes`.
This gives your functions extra arguments which match up with the parts of the routes that you have specified.
By using this, you can implement pages that change depending on this -- for example, by displaying users on a site, or documents in a repository. 

.. literalinclude:: codeexamples/variableRoutes.py

If you start the server and then visit ``http://localhost:8080/user/bob``, you should get ``Hi bob!`` in return.

You can also define what types it should match.
The three available types are ``string`` (default), ``int`` and ``float``.

.. literalinclude:: codeexamples/variableRoutesTypes.py

If you run this example and visit ``http://localhost:8080/somestring``, it will be routed by ``pg_string``, ``http://localhost:8080/1.0`` will be routed by ``pg_float`` and ``http://localhost:8080/1`` will be routed by ``pg_int``.


Route Order Matters
===================

But remember: order matters!
This becomes very important when you are using variable paths.
You can have a general, variable path, and then have hard coded paths over the top of it, such as in the following example.

.. literalinclude:: codeexamples/orderMatters.py

The later applying route for bob will overwrite the variable routing in ``pg_user``.
Any other username will be routed to ``pg_user`` as normal.


Static Files
============

To serve static files from a directory, set the ``branch`` keyword argument on the route you're serving them from to ``True``, and return a :api:`twisted.web.static.File <t.w.static.File>` with the path you want to serve.

.. literalinclude:: codeexamples/staticFiles.py

If you run this example and then visit ``http://localhost:8080/``, you will get a directory listing.


Deferreds
=========

Since it's all just Twisted underneath, you can return :api:`twisted.internet.defer.Deferred <Deferreds>`, which then fire with a result.

.. literalinclude:: codeexamples/googleProxy.py

This example here uses `treq <https://github.com/dreid/treq>`_ (think Requests, but using Twisted) to implement a Google proxy.


Return Anything
===============

Klein tries to do the right thing with what you return.
You can return a result (which can be regular text, a :api:`twisted.web.resource.IResource <Resource>`, or a :api:`twisted.web.iweb.IRenderable <Renderable>`) synchronously (via ``return``) or asynchronously (via ``Deferred``).
Just remember not to give Klein any ``unicode``, you have to encode it into ``bytes`` first.


Onwards
=======

That covers most of the general Klein concepts.
The next chapter is about deploying your Klein application using Twisted's ``tap`` functionality.
