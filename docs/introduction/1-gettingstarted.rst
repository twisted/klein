===============================
Introduction -- Getting Started
===============================

Klein is a micro-framework for developing production-ready web services with Python, built off Werkzeug and Twisted.
The purpose of this introduction is to show you how to install, use, and deploy Klein-based web applications.


This Introduction
=================

This introduction is meant as a general introduction to Klein concepts.

Everything should be as self-contained, but not everything may be runnable (for example, code that shows only a specific function).


Installing
==========

Klein is available on PyPI.
Run this to install it::

    pip install klein

.. note::

    Since Twisted is a Klein dependency, you need to have the requirements to install that as well.
    You will need the Python development headers and a working compiler - installing ``python-dev`` and ``build-essential`` on Debian, Mint, or Ubuntu should be all you need.


Hello World
===========

The following example implements a web server that will respond with "Hello, world!" when accessing the root directory.

.. literalinclude:: codeexamples/helloWorld.py

This imports ``run`` and ``route`` from the Klein package, and uses them directly.
It then starts a Twisted Web server on port 8080, listening on the loopback address.

This works fine for basic applications.
However, by creating a Klein instance, then calling the ``run`` and ``route`` methods on it, you are able to make your routing not global.

.. literalinclude:: codeexamples/helloWorldClass.py

By not using the global Klein instance, you can have different Klein routers, each having different routes, if your application requires that in the future.


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
