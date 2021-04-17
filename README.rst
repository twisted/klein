============================
Klein, a Web Micro-Framework
============================

.. image:: https://github.com/twisted/klein/workflows/CI%2fCD/badge.svg
    :target: https://github.com/twisted/klein/actions
    :alt: Build Status
.. image:: https://codecov.io/github/twisted/klein/coverage.svg?branch=master
    :target: https://codecov.io/github/twisted/klein?branch=master
    :alt: Code Coverage
.. image:: https://requires.io/github/twisted/klein/requirements.svg?branch=master
    :target: https://requires.io/github/twisted/klein/requirements/?branch=master
    :alt: Requirements Status
.. image:: https://img.shields.io/pypi/pyversions/klein.svg
    :target: https://pypi.org/project/klein
    :alt: Python Version Compatibility

Klein is a micro-framework for developing production-ready web services with Python.
It is 'micro' in that it has an incredibly small API similar to `Bottle <https://bottlepy.org/docs/dev/index.html>`_ and `Flask <https://flask.palletsprojects.com/>`_.
It is not 'micro' in that it depends on things outside the standard library.
This is primarily because it is built on widely used and well tested components like `Werkzeug <https://werkzeug.palletsprojects.com/>`_ and `Twisted <https://twistedmatrix.com>`_.

A `Klein bottle <https://en.wikipedia.org/wiki/Klein_bottle>`_ is an example of a non-orientable surface, and a glass Klein bottle looks like a twisted bottle or twisted flask.
This, of course, made it too good of a pun to pass up.

Klein's documentation can be found at `Read The Docs <https://klein.readthedocs.org>`_.


Example
========

This is a sample Klein application that returns 'Hello, world!', running on port ``8080``.

.. code-block:: python

    from klein import run, route

    @route('/')
    def home(request):
        return 'Hello, world!'

    run("localhost", 8080)


Contribute
==========

``klein`` is hosted on `GitHub <https://github.com/twisted/klein>`_ and is an open source project that welcomes contributions of all kinds from the community, including:

- code patches,
- `documentation <https://klein.readthedocs.org/>`_ improvements,
- `bug reports <https://github.com/twisted/klein/issues>`_,
- reviews for `contributed patches <https://github.com/twisted/klein/pulls>`_.

For more information about contributing, see `the contributor guidelines <https://github.com/twisted/klein/tree/master/CONTRIBUTING.rst>`_.
