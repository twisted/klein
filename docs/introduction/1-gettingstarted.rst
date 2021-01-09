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

If your file is called ``app.py``, you can start the server by running::

    python app.py

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

You can also make variable routes.
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

Streamlined Apps With HTML and JSON
===================================

For a typical web application, the first order of business is generating some
simple HTML pages that users can interact with and that search engines can
easily index.

In such an app, you'll want a consistent frame for all pages, something that
puts appropriate things into the ``<head>`` tag, like a title, references to
stylesheets and JavaScript functions, and so on.  Then, each page has its own
distinct content.

While just a little HTML might have been fine for the 90s, modern web apps
quickly - sometimes immediately - outgrow HTML though; soon you'll want some
way to get just the data from your backend out via a JSON API, often from a
dynamic JavaScript or `Python <https://brython.info>`_ front-end in the
browser.

Klein provides for this general pattern with ``klein.Plating``.

Let's build a little app that gives us some fake (random) information about
places you can go and foods you can get there. You can download the full
example :download:`here <codeexamples/template.py>` in order to run it.

First, we'll create a top-level Plating for the site.  This takes a
``twisted.web.template`` template, defined with the objects from
``twisted.web.template.tags``, with one special slot, named
``Plating.CONTENT``, in the spot where you want the content of each page to
appear.  That'll look something like this:

.. literalinclude:: codeexamples/template.py
    :lines: 15-26

Notice that we have defined a ``"pageTitle"`` slot in the template - individual
pages must each provide a value for the title themselves in order to use the
``myStyle`` frame.  Nothing's special about ``"pageTitle"``, by the way; you
may define whatever slots you want in your page template.

You can also specify a dictionary of default values to fill slots with.

Next, you want to create a route that is plated with that ``Plating``, by using
the ``Plating.routed`` decorator.  ``@myStyle.routed`` takes a route from the
Klein instance, in this case ``app``, and then a template for the content
portion (the ``Plating.CONTENT`` slot) of the page.  The decorated function
must then return a dictionary of the values to populate the slots in the
template with.

Let's start with a really simple page that just has a static template to fill
the content slot.

.. literalinclude:: codeexamples/template.py
    :lines: 29-49

This page generates some links to various sub-pages which we'll get to in a
moment.  But first, if you load ``http://localhost:8080/``, you'll see that the
template specified for ``root`` is inserted at the point in the template for
``myStyle`` specified the content should go.

Next, we should actually try injecting some data.

.. literalinclude:: codeexamples/template.py
    :lines: 52-67

Here you can see the ``/foods/...`` route for showing information about a food.
In the content template, we've got slots for ``"name"``, ``"rating"``, and
``"carbohydrates"``, the three primary properties which define a food.  The
decorated function then returns a dictionary that returns values for each of
those slots, as well as a value for ``"pageTitle"``.

Each of these slots is only filled with a single item, though.  What if you
need to put multiple items into the template?  The route for ``/places/...``
can show us:

.. literalinclude:: codeexamples/template.py
    :lines: 70-103

Here you can see the special ``<slotname>:list`` renderer in use.  By
specifying the ``render=`` attribute of a tag (in this case, a ``li`` tag) to
be ``foods:list``, we invoke a ``twisted.web.template`` renderer that repeats
the tag it is the renderer for, inserting each element of that list into the
special ``"item"`` slot.

You can view each of these pages in a web browser now, and you can see their
contents; we've built a little website that generates random values for these
types of data.  But we've *also* built a JSON API.  If you access, for example,
``http://localhost:8080/places/chicago``, you'll see an HTML view, but if you
add the query parameter ``json=1``
(e.g. ``http://localhost:8080/places/chicago?json=1``) you will see a JSON
result like this:

.. code-block:: json

    {
        "foods": [
            "pizza",
            "cheeseburgers",
            "hot dogs"
        ],
        "latitude": -32.610538480748815,
        "longitude": -9.38433633489143,
        "name": "chicago",
        "pageTitle": "Place: chicago"
    }

Any route decorated by ``@routed`` will similarly give you structured data if
you ask for it via ``?json=1``, so you can build your JSON API and your HTML
frontend at the same time.

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
========

That covers most of the general Klein concepts.
The next chapter is about deploying your Klein application using Twisted's ``tap`` functionality.
