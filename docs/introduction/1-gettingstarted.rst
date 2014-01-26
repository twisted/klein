===============================
Introduction -- Getting Started
===============================

.. note::

    **This document is still a work in progress.** Please comment on `the GitHub PR <https://github.com/twisted/klein/pull/38>`_ with any inaccuracies, comments or suggestions.

Klein is a micro-framework for developing production-ready web services with Python, built off Werkzeug and Twisted.
The purpose of this introduction is to show you how to install, use, and deploy Klein-based web applications.


This Introduction
=================

This introduction is meant as a general introduction to Klein concepts.

All of the major code snippets can be found inside `Klein's GitHub repository <https://github.com/twisted/klein/tree/master/docs/codeexamples>`_.
Everything should be as self-contained, but not everything may be runnable (for example, code that shows only a specific function).


Installing
==========

Klein is available on PyPI. Simply run this to install it::

    pip install klein

.. note::

    Since Twisted is a Klein dependency, you need to be able to install it.
    If you haven't installed Twisted before, you may need the Python development headers, contained in the Python development packages for your operating system - for example, ``python-dev`` on Debian, Mint or Ubuntu.


Hello World
===========

Here, we are not going to back down from the old introduction cliche -- let's write a Hello World application, as simply as possible.

.. literalinclude:: /codeexamples/intro1/helloWorld.py

This imports ``run`` and ``route`` from the Klein package, and uses them directly.
It then starts a Twisted Web server on port 8080, listening on the loopback address.

There is a better way to do it, however, by creating a Klein instance, then calling the ``run`` and ``route`` methods on it.

.. literalinclude:: /codeexamples/intro1/helloWorldClass.py

This also lets you have different Klein routers, each having different routes, if your application requires that in the future.


Adding Routes
=============

Adding more routes into your Klein app is easy -- just add more decorated functions.

.. literalinclude:: /codeexamples/intro1/moreRoutes.py


Variable Routes
===============

You can also make `variable routes`.

.. literalinclude:: /codeexamples/intro1/variableRoutes.py

If you start the server and then visit ``http://localhost:8080/user/bob``, you should get ``Hi bob!`` in return.

You can also define what type it should match.
The three available ones are ``string`` (default), ``int`` and ``float``.

.. literalinclude:: /codeexamples/intro1/variableRoutesTypes.py

If you run this example and visit ``http://localhost:8080/somestring``, it will be routed by ``pg_string``, ``http://localhost:8080/1.0`` will be routed by ``pg_float`` and ``http://localhost:8080/1`` will be routed by ``pg_int``.


Route Order Matters
===================

But remember: order matters!
This becomes very important when you are using variable paths.
You can have a general, variable path, and then have hard coded paths over the top of it, such as in the following example.

.. literalinclude:: /codeexamples/intro1/orderMatters.py

As you can see, the later applying route for bob will overwrite the variable routing in ``pg_user``.
Any other username will be routed to ``pg_user`` as normal.


Static Files
============

Serving static files is easy.
You need to set the ``branch`` keyword argument on the route to ``True``, and return a ``twisted.web.static.File`` with the path you want to serve.

.. literalinclude:: /codeexamples/intro1/staticFiles.py

If you run this example and then visit ``http://localhost:8080/``, you will get a directory listing.


Deferreds
=========

Since it's all just Twisted underneath, you can return Deferreds, which then return a result.

.. literalinclude:: /codeexamples/intro1/googleProxy.py

This example here uses `treq <https://github.com/dreid/treq>`_ (think Requests, but using Twisted) to implement a Google proxy.


Return Anything
===============

Klein tries to do the right thing with what you return -- you can return Deferreds or a straight result, which can be regular text, a Resource, or a Renderable.
Just remember not to give Klein any ``unicode``, you have to encode it first.


Onwards
=======

That covers most of the general Klein concepts.
The next article in the Introduction series is about deploying your Klein application using Twisted's tap functionality.