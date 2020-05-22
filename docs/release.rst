===============
Releasing Klein
===============

Klein is released on a time-dependent basis, similar to Twisted.

Each version is numbered with the major portion being the last two digits of the year, and the minor portion being the zero-indexed release number.
That is, the first release of 2016 would be 16.0, and the second would be 16.1.


Releasing Klein
---------------

#. Start with a clean (no changes) source tree on the master branch.
#. Create a new release candidate: :code:`tox -e release start`
#. Commit and push the branch
#. Open a PR from the branch (follow the usual process for opening a PR).
#. As appropriate, pull the latest code from :code:`master`: :code:`git checkout master && git pull --rebase` (or use the GitHub UI)
#. To publish a release candidate: :code:`tox -e release publish`

#. Clear the directory of any other changes using ``git clean -f -x -d  .``
#. Make a pull request for this changes.
   Continue when it is merged.
#. Generate the tarball and wheel using ``python setup.py sdist bdist_wheel``.
#. Upload the tarball and wheel using ``twine upload dist/klein-*``.
