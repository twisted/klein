============================
Klein, a Web Micro-Framework
============================

.. image:: https://travis-ci.org/twisted/klein.png?branch=master
    :target: http://travis-ci.org/twisted/klein
    :alt: Build Status
.. image:: https://codecov.io/github/codecov/codecov-ruby/coverage.svg?branch=master
    :target: https://codecov.io/github/codecov/codecov-ruby?branch=master
    :alt: Code Coverage

Klein is a microframework for developing production-ready web services with Python.

Klein's "micro" comes from its having a small, learnable API like `Flask <http://flask.pocoo.org/>`_ or `Bottle <http://bottlepy.org/docs/dev/index.html>`_.
It uses `Twisted <http://twistedmatrix.com>`_ to do asynchronous work and `Werkzeug <http://werkzeug.pocoo.org/>`_ to let you easily create a URL scheme for your users.
Twisted's asynchronous model is especially good for services where the clients can send requests to the server and use its response to confirm their local view of the world.
For example, a Twisted app for letting cartographers create and share annotations to maps stored on a server could run much faster than a synchronous app doing the same work.
Instead of waiting for a full communication cycle with the server to complete before acknowledging user actions, the asynchronous app could acknowledge user actions immediately and defer the task of acting on the server's response until that response actually arrived.

Klein's full documentation is hosted on `Read The Docs <http://klein.readthedocs.org>`_.


Example
=======

This is a sample Klein application that returns 'Hello, world!', running on port ``8080``.

.. code-block:: python

    from klein import run, route

    @route('/')
    def home(request):
        return 'Hello, world!'

    run("localhost", 8080)



Help
====

If you have questions about Klein, two of the best places to ask are Stack Overflow and IRC.
Stack Overflow's `twisted.web tag <https://stackoverflow.com/questions/tagged/twisted.web?sort=newest&show=all>`_ is a good place to ask specific questions.
You can also look for help on IRC: the Freenode channel ``#twisted.web`` has many residents with domain knowledge about Twisted.
For help about routing and the other parts of Klein provided by Werkzeug, you may want to start with `Werkzeug's community resources <http://werkzeug.pocoo.org/community/>`_.


Contribute
==========

Klein is hosted on `GitHub <http://github.com/twisted/klein>`_ and is an open source project that welcomes contributions from everybody, including:

- code patches,
- `documentation <http://klein.readthedocs.org/>`_ improvements,
- `bug reports <https://github.com/twisted/klein/issues>`_,
- reviews for `contributed patches <https://github.com/twisted/klein/pulls>`_.

For more information about contributing, see our contributor guidelines; they're available `on GitHub <https://github.com/twisted/klein/blob/master/CONTRIBUTING.rst>`_ and :ref:`on Read The Docs <contributing>`.


Report a bug
============

Like all software, Klein is imperfect.
We appreciate it when you `report problems you've had with Klein <https://github.com/twisted/klein/issues/new>`_.
You can see other problems that people have reported on the `GitHub Issues page <https://github.com/twisted/klein/issues>`_.
If the problem you're having is the same as one of the existing issues, please add a comment to that issue.


Why "Klein"?
============

.. image:: https://upload.wikimedia.org/wikipedia/commons/thumb/2/21/Acme_klein_bottle.jpg/176px-Acme_klein_bottle.jpg
   :target: https://en.wikipedia.org/wiki/File:Acme_klein_bottle.jpg
   :alt: A glass Klein bottle
   :align: right

A `Klein bottle <https://en.wikipedia.org/wiki/Klein_bottle>`_ is a topological curiousity that looks like a twisted bottle or twisted flask.
This, of course, made it too good of a pun to pass up.
