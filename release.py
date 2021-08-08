# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from enum import Enum
from os import chdir
from pathlib import Path
from shutil import rmtree
from subprocess import CalledProcessError, run
from sys import exit, stderr
from tempfile import mkdtemp
from typing import Any, Dict, NoReturn, Optional, Sequence, cast

from click import group as commandGroup
from click import option as commandOption
from git import Repo as Repository
from git import TagReference
from git.refs.head import Head
from incremental import Version


class PyPI(Enum):
    Test = "testpypi"
    Production = "pypi"


def warning(message: str) -> None:
    """
    Print a warning.
    """
    print(f"WARNING: {message}", file=stderr)


def error(message: str, exitStatus: int) -> NoReturn:
    """
    Print an error message and exit with the given status.
    """
    print(f"ERROR: {message}", file=stderr)
    exit(exitStatus)


def spawn(args: Sequence[str]) -> None:
    """
    Spawn a new process with the given arguments, raising L{SystemExit} with
    captured output if the exit status is non-zero.
    """
    print("Executing command:", " ".join(repr(arg) for arg in args))
    try:
        run(args, input=b"", capture_output=True, check=True)
    except CalledProcessError as e:
        error(f"command {e.cmd} failed: {e.stderr}", 1)


def currentVersion() -> Version:
    """
    Determine the current version.
    """
    # Incremental doesn't have an API to do this, so we are duplicating some
    # code from its source tree. Boo.
    versionInfo: Dict[str, Any] = {}
    versonFile = Path(__file__).parent / "src" / "klein" / "_version.py"
    exec(versonFile.read_text(), versionInfo)
    return versionInfo["__version__"]


def fadeToBlack() -> None:
    """
    Run black to reformat the source code.
    """
    spawn(["tox", "-e", "black-reformat"])


def incrementVersion(candidate: bool) -> None:
    """
    Increment the current release version.
    If C{candidate} is C{True}, the new version will be a release candidate;
    otherwise it will be a regular release.
    """
    # Incremental doesn't have an API to do this, so we have to run a
    # subprocess. Boo.
    args = ["python", "-m", "incremental.update", "klein"]
    if candidate:
        args.append("--rc")
    spawn(args)

    # Incremental generates code that black wants to reformat.
    fadeToBlack()


def releaseBranchName(version: Version) -> str:
    """
    Compute the name of the release branch for the given version.
    """
    return f"release-{version.major}.{version.minor}"


def releaseBranch(repository: Repository, version: Version) -> Optional[Head]:
    """
    Return the release branch corresponding to the given version.
    """
    branchName = releaseBranchName(version)

    if branchName in repository.heads:
        return repository.heads[branchName]

    return None


def releaseTagName(version: Version) -> str:
    """
    Compute the name of the release tag for the given version.
    """
    return cast(str, version.public())


def createReleaseBranch(repository: Repository, version: Version) -> Head:
    """
    Create a new release branch.
    """
    branchName = releaseBranchName(version)

    if branchName in repository.heads:
        error(f'Release branch "{branchName}" already exists.', 1)

    print(f'Creating release branch: "{branchName}"')
    return repository.create_head(branchName)


def clone(repository: Repository, tag: TagReference) -> Path:
    """
    Clone a tagged version from the given repository's origin.
    Return the path to the new clone.
    """
    path = Path(mkdtemp())

    print(f"Cloning repository with tag {tag} at {path}...")
    Repository.clone_from(
        url=next(repository.remotes.origin.urls),
        to_path=str(path),
        branch=tag.name,
        multi_options=["--depth=1"],
    )

    return path


def distribute(
    repository: Repository, tag: TagReference, test: bool = False
) -> None:
    """
    Build a distribution for the project at the given path and upload to PyPI.
    """
    src = clone(repository, tag)

    if test:
        pypi = PyPI.Test
    else:
        pypi = PyPI.Production

    wd = Path.cwd()
    try:
        chdir(src)

        print("Building distribution at:", src)
        spawn(["python", "setup.py", "sdist", "bdist_wheel"])

        print(f"Uploading distribution to {pypi.value}...")
        twineCommand = ["twine", "upload"]
        twineCommand.append(f"--repository={pypi.value}")
        twineCommand += [str(p) for p in Path("dist").iterdir()]
        spawn(twineCommand)

    finally:
        chdir(wd)

    rmtree(str(src))


def startRelease() -> None:
    """
    Start a new release:
     * Increment the current version to a new release candidate version.
     * Create a corresponding branch.
     * Switch to the new branch.
    """
    repository = Repository()

    if repository.head.ref != repository.heads.master:
        error(
            f"working copy is from non-master branch: {repository.head.ref}", 1
        )

    if repository.is_dirty():
        warning("working copy is dirty")

    version = currentVersion()

    if version.release_candidate is not None:
        error(f"current version is already a release candidate: {version}", 1)

    incrementVersion(candidate=True)
    version = currentVersion()

    print(f"New release candidate version: {version.public()}")

    branch = createReleaseBranch(repository, version)
    branch.checkout()

    print("Next steps (to be done manually):")
    print(" • Commit version changes to the new release branch:", branch)
    print(" • Push the release branch to GitHub")
    print(" • Open a pull request on GitHub from the release branch")


def bumpRelease() -> None:
    """
    Increment the release candidate version.
    """
    repository = Repository()

    if repository.is_dirty():
        warning("working copy is dirty")

    version = currentVersion()

    if version.release_candidate is None:
        error(f"current version is not a release candidate: {version}", 1)

    branch = releaseBranch(repository, version)

    if repository.head.ref != branch:
        error(
            f'working copy is on branch "{repository.head.ref}", '
            f'not release branch "{branch}"',
            1,
        )

    incrementVersion(candidate=True)
    version = currentVersion()

    print("New release candidate version:", version.public())


def publishRelease(final: bool, test: bool = False) -> None:
    """
    Publish the current version.
    """
    repository = Repository()

    if repository.is_dirty():
        error("working copy is dirty", 1)

    version = currentVersion()

    if version.release_candidate is None:
        error(f"current version is not a release candidate: {version}", 1)

    branch = releaseBranch(repository, version)

    if repository.head.ref != branch:
        error(
            f'working copy is on branch "{repository.head.ref}", '
            f'not release branch "{branch}"',
            1,
        )

    incrementVersion(candidate=False)
    version = currentVersion()

    versonFile = Path(__file__).parent / "src" / "klein" / "_version.py"
    repository.index.add(str(versonFile))
    repository.index.commit(f"Update version to {version}")

    tagName = releaseTagName(version)

    if tagName in repository.tags:
        tag = repository.tags[tagName]
        message = f"Release tag already exists: {tagName}"
        if tag.commit != repository.head.ref.commit:
            error(message, 1)
        else:
            print(message)
    else:
        print("Creating release tag:", tagName)
        tag = repository.create_tag(
            tagName, ref=branch, message=f"Tag release {version.public()}"
        )

    print("Pushing tag to origin:", tag)
    repository.remotes.origin.push(refspec=tag.path)

    distribute(repository, tag, test=test)


@commandGroup()
def main() -> None:
    pass


@main.command()
def start() -> None:
    startRelease()


@main.command()
def bump() -> None:
    bumpRelease()


@main.command()
@commandOption(
    "--test/--production", help="Use test (or production) PyPI server"
)
@commandOption(
    "--final/--candidate", help="Publish a final (or candidate) release"
)
def publish(final: bool, test: bool) -> None:
    publishRelease(final=final, test=test)


if __name__ == "__main__":
    main()
