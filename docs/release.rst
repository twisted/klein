===============
Releasing Klein
===============

Klein is released on a time-dependent basis, similar to Twisted.

Each version is numbered with the major portion being the last two digits of the year, and the minor portion being the zero-indexed release number.
That is, the first release of 2016 would be 16.0, and the second would be 16.1.


Releasing Klein
---------------

#. Start with a clean (no changes) source tree on the trunk branch.
#. Create a new release candidate: :code:`tox -e release -- start`
#. Manually update the ``NEXT`` heading in ``NEWS.rst`` to reference the
   version that was just updated, *without* the "rc" release-candidate tag, and
   the current RFC3339-formatted date; i.e. write the ``NEWS.rst`` file as if
   it were for the final release.
#. Commit and push the branch
#. Open a PR from the branch (follow the usual process for opening a PR).
#. As appropriate, pull the latest code from :code:`trunk`: :code:`git checkout
   trunk && git pull --rebase` (or use the GitHub UI)
#. To publish a release candidate to PyPI: :code:`tox -e release -- publish --candidate`
#. Obtain an approving review for the PR using the usual process.
#. If the date has changed since the release candidate, update the RFC3339 date
   in the ``NEWS.rst`` header for the release to the current date; commit and
   push this change to the branch.
#. Publish a production release with the command: :code:`tox -e release --
   publish --final`
#. In ``NEWS.rst``, add a new "NEXT" section at the top.  You do not need a
   separate review for this addition; it should be done after the release, but
   before merging to trunk.
#. Merge the PR to the trunk branch.
