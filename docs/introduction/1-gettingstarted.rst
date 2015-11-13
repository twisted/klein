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

Once you have a Klein instance, you can tell it how to handle more URLs by defining more functions decorated with ``@route``.

.. literalinclude:: codeexamples/moreRoutes.py

You can also use variables in route definitions.
When the path passed to ``@route`` includes variables, Klein passes keyword arguments with the same names as those variables to your route functions.
Use angle brackets around parts of the path to indicate that they should be treated as variables.

.. literalinclude:: codeexamples/variableRoutes.py

With this example, when you start the server and visit ``http://localhost:8080/user/bob``, the server should return ``Hi bob!``.

Variables in route definitions can also have a converter attached to them.
This lets you express constraints on what kinds of input will match the route.
Add these constraints by prefixing your variable name with the name of a converter.
Here is an example that uses the ``string``, ``float``, and ``int`` converters to dispatch a request to different endpoints based on what the the requested path can be converted to.

.. literalinclude:: codeexamples/variableRoutesTypes.py

In this example,  will be  by ``pg_string``, ``http://localhost:8080/1.0`` will be routed by ``pg_float`` and ``http://localhost:8080/1`` will be routed by ``pg_int``.




Using variables in routes lets you can implement pages that change depending on this -- for example, by displaying users on a site, or documents in a repository.

You can also define what types it should match.
The three available types are ``string`` (default), ``int`` and ``float``.
.. more types! werkzeug's been updated :)

.. http://werkzeug.pocoo.org/docs/0.10/routing/#builtin-converters



.. watch out for this: werkzeug route weighting is complicated

.. note::

   Route order matters!
   This is important when you are using variable paths.
   You can have a general, variable path, and then have hard coded paths over the top of it, such as in the following example.

   .. literalinclude:: codeexamples/orderMatters.py

   The route for bob will overwrite the variable routing in ``pg_user``.
   Any other username will be routed to ``pg_user`` as normal.

   .. TODO: reconcile this with the other thing about route order, in the "handling POST" example

   .. TODO: add a note about the https://github.com/twisted/klein/issues/41 behavior, mention that issue in the pull request

   .. TODO: When reading or adding to the table of URI-to-resource routes,
      remember that Werkzeug's implementation requires that the longest or
      most-specific URIs be dealt with last. Wait, no, Werkzeug gives routes
      weights and it's complicated and ugh. D: cf
      https://github.com/mitsuhiko/werkzeug/blob/master/werkzeug/routing.py#L855
      in summary: AUGH

Static Files
============

To serve static files from a directory, set the ``branch`` keyword argument on the route you're serving them from to ``True``, and return a :api:`twisted.web.static.File <t.w.static.File>` with the path you want to serve.

.. literalinclude:: codeexamples/staticFiles.py

If you run this example and then visit ``http://localhost:8080/``, you will get a directory listing.


Deferreds
=========

Since it's all just Twisted underneath, you can return :api:`twisted.internet.defer.Deferred <Deferreds>`, which then fire with a result.

.. literalinclude:: codeexamples/googleProxy.py

This example here uses `treq <https://github.com/twisted/treq>`_ (think Requests, but using Twisted) to implement a Google proxy.


Return Anything
===============

Klein tries to do the right thing with what you return.
You can return a result (which can be regular text, a :api:`twisted.web.resource.IResource <Resource>`, or a :api:`twisted.web.iweb.IRenderable <Renderable>`) synchronously (via ``return``) or asynchronously (via ``Deferred``).
Just remember not to give Klein any ``unicode``, you have to encode it into ``bytes`` first.


Next Steps
==========

That covers most of the general Klein concepts.
The next chapter is about deploying your Klein application using Twisted's ``tap`` functionality.
