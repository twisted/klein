=====================
Contributing to Klein
=====================

Klein is an open source project, with contributions of all kinds coming from the community.

These include:

- code patches
- `documentation <http://klein.readthedocs.org/>`_ improvements
- `bug reports <https://github.com/twisted/klein/issues>`_
- reviews for `contributed patches <https://github.com/twisted/klein/pulls>`_

Here's some suggestions to make the contributing process much smoother:

Code
====

- Propose all patches through a pull request in the `GitHub repo <https://github.com/twisted/klein>`_.
- Use `Twisted's code style guide <http://twistedmatrix.com/documents/current/core/development/policy/coding-standard.html>`_ for all code you touch, as long as it doesn't break a public API.
- Make sure your patch has tests, since untested code is buggy code.
- If it's a new feature, add an example under ``docs/examples/`` and add it to the index.
- Add yourself to ``AUTHORS``.
- Put ``[WIP]`` in the title if it's a work in progress pull request.


Documentation
=============

- The header order::

    ========
    Header 1
    ========

    Header 2
    ========

    Header 3
    --------

    Header 4
    ~~~~~~~~
- Use gender-neutral pronouns, if you have to at all.
- Put each sentence on a different line, if you can -- this makes diffs much easier to read.
  You will need to add an indent to make it continue lists.


Reviewing
=========

All code that goes into Klein must be reviewed by at least one other person who is not an author of the patch.
This can help prevent bugs from slipping through the net, gives another source for improvements, and makes sure that the code meets standard.

Reviewers should read `Glyph's mailing list post <http://twistedmatrix.com/pipermail/twisted-python/2014-January/027894.html>`_ on reviewing -- code and docs don't have to be *perfect*, only *better*.