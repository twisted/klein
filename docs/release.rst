===============
Releasing Klein
===============

Klein is released on a time-dependent basis, similar to Twisted.

Each version is numbered with the major portion being the last two digits of the year, and the minor portion being the zero-indexed release number.
That is, the first release of 2016 would be 16.0, and the second would be 16.1.


Doing a Release
---------------

#. Create a branch called "release-<version>"
#. Run :code:`python incremental.update Klein --rc && python incremental.update Klein`
#. Commit, and push the branch
#. Open a PR from the branch (follow the usual process for merging a PR).
#. Pull latest :code:`master`: :code:`git checkout master && git pull --rebase`
#. Clear the directory of any other changes using ``git clean -f -x -d  .``
#. Tag the release using ``git tag -s <release> -m "Tag <release> release"``
#. Push up the tag using ``git push --tags``.
#. Make a pull request for this changes.
   Continue when it is merged.
#. Generate the tarball and wheel using ``python setup.py sdist bdist_wheel``.
#. Upload the tarball and wheel using ``twine upload dist/klein-*``.
