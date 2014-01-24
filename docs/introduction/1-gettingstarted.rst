===============================
Introduction -- Getting Started
===============================

things we should talk about here:

- show the most basic example (like the readme)
- add some more routes, demonstrate how order matters
- return some deferreds (maybe use treq?)
- serve some basic static files

Klein is a micro-framework for developing production ready web services with Python, built off Werkzeug and Twisted.
The purpose of this introduction is to show you how to install, use and deploy Klein-based web applications.


This Introduction
=================

All of the major code snippets can be found inside `Klein's GitHub repository <https://github.com/twisted/klein>`_, under ``docs/codeexamples``.
Everything should be as self-contained as possible, but it may not be runnable.


Installing
==========

Klein is available on PyPI. Simply run this to install it::

    pip install klein

It will pull in Twisted and Werkzeug as dependencies.
Note that if you haven't installed Twisted before, you may need the Python development headers.
These are contained in the Python development packages for your operating system - for example, ``python-dev`` on Debian.


Hello World
===========

Here, we are not going to back down from the old introduction cliche - let's write a Hello World, as simply as possible.

.. literalinclude:: /codeexamples/intro1/helloWorld.py

This imports ``run`` and ``route`` from the Klein package, and uses them directly.
It then starts a Twisted Web server on port 8080, listening on the loopback address.

There is a better way to do it, however, by creating a Klein object, and then calling the ``run`` and ``route`` methods on it.

.. literalinclude:: /codeexamples/intro1/helloWorldClass.py

This also lets you have different Klein routers, each having different routes, if your application requires that in the future.


More Routes
===========

Adding more routes into your Klein app is easy - just add more decorated functions.

.. literalinclude:: /codeexamples/intro1/moreRoutes.py

But remember - order matters! This becomes very important when you are using variable paths! (More on them soon.)

.. literalinclude:: /codeexamples/intro1/orderMatters.py