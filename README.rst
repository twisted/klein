============================
Klein, a Web Micro-Framework
============================

.. image:: https://travis-ci.org/twisted/klein.png?branch=master
    :target: http://travis-ci.org/twisted/klein
    :alt: Build Status

Klein is a micro-framework for developing production-ready web services with Python.
It is 'micro' in that it has an incredibly small API similar to `Bottle <http://bottlepy.org/docs/dev/index.html>`_ and `Flask <http://flask.pocoo.org/>`_.
It is not 'micro' in that it depends on things outside the standard library.
This is primarily because it is built on widely used and well tested components like `Werkzeug <http://werkzeug.pocoo.org/>`_ and `Twisted <http://twistedmatrix.com>`_.


Klein's documentation can be found at `Read The Docs <http://klein.readthedocs.org>`_.


Example
=======

This is a sample Klein application that returns 'Hello, world!', running on port ``8080``.

.. code-block:: python

    from klein import run, route

    @route('/')
    def home(request):
        return 'Hello, world!'

    run("localhost", 8080)


Contribute
==========

``klein`` is hosted on `GitHub <http://github.com/twisted/klein>`_ and is an open source project that welcomes contributions of all kinds from the community, including:

- code patches,
- `documentation <http://klein.readthedocs.org/>`_ improvements,
- `bug reports <https://github.com/twisted/klein/issues>`_,
- reviews for `contributed patches <https://github.com/twisted/klein/pulls>`_.

For more information about contributing, see `the contributor guidelines <https://github.com/twisted/klein/tree/master/CONTRIBUTING.rst>`_.


Help
====

If you have questions about Klein, two of the best places to ask are Stack Overflow and IRC.
Stack Overflow's `twisted.web tag <http://stackoverflow.com/questions/new/twisted.web?show=all&sort=newest>`_ is a good place to ask specific questions.
You can also look for help on IRC: the Freenode channel ``#twisted.web`` has many residents with domain knowledge about Twisted.
For help about routing and the other parts of Klein provided by Werkzeug, you may want to start with `Werkzeug's community resources <http://werkzeug.pocoo.org/community/>`_.


Report a bug
============

Like all software, Klein is imperfect.
We appreciate it when you `report problems you've had with Klein <https://github.com/twisted/klein/issues/new>`_.
You can see other problems that people have reported on the `GitHub Issues page <https://github.com/twisted/klein/issues>`_.
If the problem you're having is the same as one of the existing issues, please add a comment to that issue.


Name
====

.. image:: https://upload.wikimedia.org/wikipedia/commons/thumb/2/21/Acme_klein_bottle.jpg/176px-Acme_klein_bottle.jpg
   :target: https://en.wikipedia.org/wiki/File:Acme_klein_bottle.jpg
   :alt: A glass Klein bottle

A `Klein bottle <https://en.wikipedia.org/wiki/Klein_bottle>`_ is a topological curiousity that looks like a twisted bottle or twisted flask.
This, of course, made it too good of a pun to pass up.
