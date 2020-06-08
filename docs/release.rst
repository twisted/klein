===============
Releasing Klein
===============

Klein is released on a time-dependent basis, similar to Twisted.

Each version is numbered with the major portion being the last two digits of the year, and the minor portion being the zero-indexed release number.
That is, the first release of 2016 would be 16.0, and the second would be 16.1.


Releasing Klein
---------------

#. Start with a clean (no changes) source tree on the master branch.
#. Create a new release candidate: :code:`tox -e release -- start`
#. Commit and push the branch
#. Open a PR from the branch (follow the usual process for opening a PR).
#. As appropriate, pull the latest code from :code:`master`: :code:`git checkout master && git pull --rebase` (or use the GitHub UI)
#. To publish a release candidate to PyPI: :code:`tox -e release -- publish`
#. Obtain an approving review for the PR using the usual process.
#. To publish a production release: :code:`tox -e release -- publish --final`
#. Merge the PR to the master branch.
