=====================
Contributing to Klein
=====================

Here's some suggestions to get a patch into Klein.

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
- Put each sentence on a different line, if you can -- this makes diffs much easier to read. You won't be able to in, for example, lists, but that's fine.