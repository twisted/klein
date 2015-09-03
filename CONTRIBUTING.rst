=====================
Contributing to Klein
=====================

Klein is an open source project that welcomes contributions of all kinds coming from the community, including:

- code patches,
- `documentation <http://klein.readthedocs.org/>`_ improvements,
- `bug reports <https://github.com/twisted/klein/issues>`_,
- reviews for `contributed patches <https://github.com/twisted/klein/pulls>`_.


Getting started
===============

Here is a list of shell commands that will install the dependencies of Klein, run the test suite, and compile the documentation.

::
   pip install --user -r requirements.txt
   tox
   tox -e docs


Next steps
----------

Here are some suggestions to make the contributing process easier for everyone:

Code
----

- Propose all patches through a pull request in the `GitHub repo <https://github.com/twisted/klein>`_.
- Use `Twisted's coding standards <http://twistedmatrix.com/documents/current/core/development/policy/coding-standard.html>`_ as a guideline for code changes you make.
- Code changes should have tests: untested code is buggy code.
  Klein uses `Twisted Trial <http://twistedmatrix.com/documents/current/api/twisted.trial.html>`_ and `tox <https://testrun.org/tox/latest/index.html>`_ for its tests.
  The command to run the full test suite is ``tox`` with no arguments.
  This will run tests against several versions of Python and Twisted, which can be time-consuming.
  To run tests against only one or a few versions, pass a ``-e`` argument with an environment from the envlist in ``tox.ini``: for example, ``tox -e py27-tw150`` will run tests with Python 2.7 and Twisted 15.0.
  To run only one or a few specific tests in the suite, add a filename or fully-qualified Python path to the end of the test invocation: for example, ``tox klein.test.test_app.KleinTestCase.test_foo`` will run only the ``test_foo()`` method of the ``KleinTestCase`` class in ``klein/test/test_app.py``.
  These two test shortcuts can be combined to give you a quick feedback cycle, but make sure to check on the full test suite from time to time to make sure changes haven't had unexpected side effects.
- If you're adding a new feature, please add an example and some explanation to the `examples directory <https://github.com/twisted/klein/tree/master/docs/examples>`_, then add your example to the index.
- Please run `flake8 <https://flake8.readthedocs.org/>`_ or a similar tool on any changed code.
  Such tools expose many small-but-common errors early enough that it's easy to remedy the problem.
- Add yourself to ``AUTHORS``.
  Your contribution matters.
- If your pull request is a work in progress, please put ``[WIP]`` in its title.


Documentation
-------------

Klein uses `Epydoc <http://epydoc.sourceforge.net/manual-epytext.html>`_ for docstrings in code and uses `Sphinx <http://sphinx-doc.org/latest/index.html>`_ for standalone documentation.

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
- In prose, please use gender-neutral pronouns or structure sentences such that using pronouns is unecessary.
- It's best to put each sentence on a different line: this makes diffs much easier to read.
  Sentences that are part of list items need to be indented to be considered part of the same list item.


Reviewing
---------

All code changes added to Klein must be reviewed by at least one other person who is not an author of the code being added.
This helps prevent bugs from slipping through the net, gives another source for improvements, and makes sure that the code productively follows guidelines.

Reviewers should read `Glyph's mailing list post <http://twistedmatrix.com/pipermail/twisted-python/2014-January/027894.html>`_ on reviewing -- code and docs don't have to be *perfect*, only *better*.
