=====================
Contributing to Klein
=====================

Klein is an open source project that welcomes contributions of all kinds coming from the community, including:

- code patches,
- `documentation <https://klein.readthedocs.io/en/latest/>`_ improvements,
- `bug reports <https://github.com/twisted/klein/issues>`_,
- reviews for `contributed patches <https://github.com/twisted/klein/pulls>`_.


Getting started
===============

Here is a list of shell commands that will install the dependencies of Klein, run the test suite with Python 3.8 and the current version of Twisted, compile the documentation, and check for coding style issues with flake8.

.. code-block:: shell

   pip install --user tox
   tox -e py38-twcurrent
   tox -e docs
   tox -e flake8

`Tox <https://tox.readthedocs.io/en/latest/>`_ makes a virtualenv, installs Klein's dependencies into the virtualenv, and then runs a set of commands based on the ``-e`` (environment) argument.
This strategy allows one to make and test changes to Klein without needing to change system-level Python packages.


Next steps
==========

Here are some suggestions to make the contributing process easier for everyone:

Code
----

- Use `Twisted's coding standards <https://twistedmatrix.com/documents/current/core/development/policy/coding-standard.html>`_ as a guideline for code changes you make.
  Some parts of Klein (eg. ``klein.resource.ensure_utf8_bytes``) do not adhere to the Twisted style guide, but changing that would break public APIs, which is worse than breaking the style guidelines.
  Similarly, if you change existing code, following the Twisted style guide is good, but is less important than not breaking public APIs.
- Compatibility across versions is important: here are `Twisted's compatibility guidelines <https://twistedmatrix.com/trac/wiki/CompatibilityPolicy>`_, which Klein shares.
- If you're adding a new feature, please add a file with an example and some explanation to the `examples directory <https://github.com/twisted/klein/tree/master/docs/examples>`_, then add your example to ``/docs/index.rst``.
- Please run ``tox -e flake8`` to check for style issues in changed code.
  Flake8 and similar tools expose many small-but-common errors early enough that it's easy to remedy the problem.
- Code changes should have tests: untested code is buggy code.
  Klein uses `Twisted Trial <https://twistedmatrix.com/documents/current/api/twisted.trial.html>`_ and `tox <https://tox.readthedocs.io/en/latest/>`_ for its tests.
  The command to run the full test suite is ``tox`` with no arguments.
  This will run tests against several versions of Python and Twisted, which can be time-consuming.
  To run tests against only one or a few versions, pass a ``-e`` argument with an environment from the envlist in ``tox.ini``: for example, ``tox -e py38-twcurrent`` will run tests with Python 3.8 and the current released version of Twisted.
  To run only one or a few specific tests in the suite, add a filename or fully-qualified Python path to the end of the test invocation: for example, ``tox klein.test.test_app.KleinTestCase.test_foo`` will run only the ``test_foo()`` method of the ``KleinTestCase`` class in ``klein/test/test_app.py``.
  These two test shortcuts can be combined to give you a quick feedback cycle, but make sure to check on the full test suite from time to time to make sure changes haven't had unexpected side effects.
- Show us your code changes through pull requests sent to `Klein's GitHub repo <https://github.com/twisted/klein>`_.
  This is the best way to make your code visible to others and to get feedback about it.
- If your pull request is a work in progress, please put ``[WIP]`` in its title.
- Add yourself to ``AUTHORS``.
  **Your contribution matters.**


Documentation
-------------

Klein uses `Epydoc <http://epydoc.sourceforge.net/manual-epytext.html>`_ for docstrings in code and uses `Sphinx <https://www.sphinx-doc.org/en/master/>`_ for standalone documentation.

- In documents with headers, use this format and order for headers::

    ========
    Header 1
    ========

    Header 2
    ========

    Header 3
    --------

    Header 4
    ~~~~~~~~
- In prose, please use gender-neutral pronouns or structure sentences such that using pronouns is unnecessary.
- It's best to put each sentence on a different line: this makes diffs much easier to read.
  Sentences that are part of list items need to be indented to be considered part of the same list item.


Reviewing
---------

All code changes added to Klein must be reviewed by at least one other person who is not an author of the code being added.
This helps prevent bugs from slipping through the net, gives another source for improvements, and makes sure that the code productively follows guidelines.

Reviewers should read `Glyph's mailing list post <https://twistedmatrix.com/pipermail/twisted-python/2014-January/027894.html>`_ on reviewing -- code and docs don't have to be *perfect*, only *better*.
