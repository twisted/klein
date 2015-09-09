# Copyright (c) 2013-2014, Aaron Gallagher <_@habnab.it>
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
# REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
# AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
# INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
# LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
# OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
# PERFORMANCE OF THIS SOFTWARE.

"""Simplify your python project versioning.

In-depth docs online: https://vcversioner.readthedocs.org/en/latest/
Code online: https://github.com/habnabit/vcversioner

"""

from __future__ import print_function, unicode_literals

import collections
import os
import subprocess
import warnings


Version = collections.namedtuple('Version', 'version commits sha')


_print = print
def print(*a, **kw):
    _print('vcversioner:', *a, **kw)


def _fix_path(p):
    "Translate ``/``s into the right path separator."
    return p.replace('/', os.sep)


_vcs_args_by_path = [
    ('%(root)s/.git', (
        'git', '--git-dir', '%(root)s/.git', 'describe', '--tags', '--long')),
    ('%(root)s/.hg', (
        'hg', 'log', '-R', '%(root)s', '-r', '.', '--template',
        '{latesttag}-{latesttagdistance}-hg{node|short}')),
]


def find_version(include_dev_version=True, root='%(pwd)s',
                 version_file='%(root)s/version.txt', version_module_paths=(),
                 git_args=None, vcs_args=None, decrement_dev_version=None,
                 strip_prefix='v',
                 Popen=subprocess.Popen, open=open):
    """Find an appropriate version number from version control.

    It's much more convenient to be able to use your version control system's
    tagging mechanism to derive a version number than to have to duplicate that
    information all over the place.

    The default behavior is to write out a ``version.txt`` file which contains
    the VCS output, for systems where the appropriate VCS is not installed or
    there is no VCS metadata directory present. ``version.txt`` can (and
    probably should!) be packaged in release tarballs by way of the
    ``MANIFEST.in`` file.

    :param include_dev_version: By default, if there are any commits after the
        most recent tag (as reported by the VCS), that number will be included
        in the version number as a ``.post`` suffix. For example, if the most
        recent tag is ``1.0`` and there have been three commits after that tag,
        the version number will be ``1.0.post3``. This behavior can be disabled
        by setting this parameter to ``False``.

    :param root: The directory of the repository root. The default value is the
        current working directory, since when running ``setup.py``, this is
        often (but not always) the same as the current working directory.
        Standard substitutions are performed on this value.

    :param version_file: The name of the file where version information will be
        saved. Reading and writing version files can be disabled altogether by
        setting this parameter to ``None``. Standard substitutions are
        performed on this value.

    :param version_module_paths: A list of python modules which will be
        automatically generated containing ``__version__`` and ``__sha__``
        attributes. For example, with ``package/_version.py`` as a version
        module path, ``package/__init__.py`` could do ``from package._version
        import __version__, __sha__``.

    :param git_args: **Deprecated.** Please use *vcs_args* instead.

    :param vcs_args: The command to run to get a version. By default, this is
        automatically guessed from directories present in the repository root.
        Specify this as a list of string arguments including the program to
        run, e.g. ``['git', 'describe']``. Standard substitutions are performed
        on each value in the provided list.

    :param decrement_dev_version: If ``True``, subtract one from the number of
        commits after the most recent tag. This is primarily for hg, as hg
        requires a commit to make a tag. If the VCS used is hg (i.e. the
        revision starts with ``'hg'``) and *decrement_dev_version* is not
        specified as ``False``, *decrement_dev_version* will be set to
        ``True``.

    :param strip_prefix: A string which will be stripped from the start of
        version number tags. By default this is ``'v'``, but could be
        ``'debian/'`` for compatibility with ``git-dch``.

    :param Popen: Defaults to ``subprocess.Popen``. This is for testing.

    :param open: Defaults to ``open``. This is for testing.

    *root*, *version_file*, and *git_args* each support some substitutions:

    ``%(root)s``
      The value provided for *root*. This is not available for the *root*
      parameter itself.

    ``%(pwd)s``
      The current working directory.

    ``/`` will automatically be translated into the correct path separator for
    the current platform, such as ``:`` or ``\``.

    ``vcversioner`` will perform automatic VCS detection with the following
    directories, in order, and run the specified commands.

       ``%(root)s/.git``

          ``git --git-dir %(root)s/.git describe --tags --long``. ``--git-dir``
          is used to prevent contamination from git repositories which aren't
          the git repository of your project.

       ``%(root)s/.hg``

          ``hg log -R %(root)s -r . --template
          '{latesttag}-{latesttagdistance}-hg{node|short}'``. ``-R`` is
          similarly used to prevent contamination.

    """

    substitutions = {'pwd': os.getcwd()}
    substitutions['root'] = root % substitutions
    def substitute(val):
        return _fix_path(val % substitutions)
    if version_file is not None:
        version_file = substitute(version_file)

    if git_args is not None:
        warnings.warn(
            'passing `git_args is deprecated; please use vcs_args',
            DeprecationWarning)
        vcs_args = git_args

    if vcs_args is None:
        for path, args in _vcs_args_by_path:
            if os.path.exists(substitute(path)):
                vcs_args = args
                break

    raw_version = None
    vcs_output = []

    if vcs_args is not None:
        vcs_args = [substitute(arg) for arg in vcs_args]

        # try to pull the version from some VCS, or (perhaps) fall back on a
        # previously-saved version.
        try:
            proc = Popen(vcs_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError:
            pass
        else:
            stdout, stderr = proc.communicate()
            raw_version = stdout.strip().decode()
            vcs_output = stderr.decode().splitlines()
            version_source = 'VCS'
        failure = '%r failed' % (vcs_args,)
    else:
        failure = 'no VCS could be detected in %(root)r' % substitutions

    def show_vcs_output():
        if not vcs_output:
            return
        print('-- VCS output follows --')
        for line in vcs_output:
            print(line)

    # VCS failed if the string is empty
    if not raw_version:
        if version_file is None:
            print('%s.' % (failure,))
            show_vcs_output()
            raise SystemExit(2)
        elif not os.path.exists(version_file):
            print("%s and %r isn't present." % (failure, version_file))
            print("are you installing from a github tarball?")
            show_vcs_output()
            raise SystemExit(2)
        with open(version_file, 'rb') as infile:
            raw_version = infile.read().decode()
        version_source = repr(version_file)


    # try to parse the version into something usable.
    try:
        tag_version, commits, sha = raw_version.rsplit('-', 2)
    except ValueError:
        print("%r (from %s) couldn't be parsed into a version." % (
            raw_version, version_source))
        show_vcs_output()
        raise SystemExit(2)

    # remove leading prefix
    if tag_version.startswith(strip_prefix):
        tag_version = tag_version[len(strip_prefix):]

    if version_file is not None:
        with open(version_file, 'w') as outfile:
            outfile.write(raw_version)

    if sha.startswith('hg') and decrement_dev_version is None:
        decrement_dev_version = True

    if decrement_dev_version:
        commits = str(int(commits) - 1)

    if commits == '0' or not include_dev_version:
        version = tag_version
    else:
        version = '%s.post%s' % (tag_version, commits)

    for path in version_module_paths:
        with open(path, 'w') as outfile:
            outfile.write("""
# This file is automatically generated by setup.py.
__version__ = {0}
__sha__ = {1}
__revision__ = {1}
""".format(repr(version).lstrip('u'), repr(sha).lstrip('u')))

    return Version(version, commits, sha)


def setup(dist, attr, value):
    """A hook for simplifying ``vcversioner`` use from distutils.

    This hook, when installed properly, allows vcversioner to automatically run
    when specifying a ``vcversioner`` argument to ``setup``. For example::

      from setuptools import setup

      setup(
          setup_requires=['vcversioner'],
          vcversioner={},
      )

    The parameter to the ``vcversioner`` argument is a dict of keyword
    arguments which :func:`find_version` will be called with.

    """

    dist.version = dist.metadata.version = find_version(**value).version
