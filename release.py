from pathlib import Path
from subprocess import CalledProcessError, run
from sys import exit, stderr
from typing import Any, Dict, NoReturn, Optional, Sequence

from click import command, group as commandGroup

from git import Repo as Repository
from git.refs.head import Head

from incremental import Version


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
    Spawn a new process with the given arguments, raising L{CalledProcessError}
    with captured output if the exit status is non-zero.
    """
    try:
        run(args, capture_output=True, check=True)
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
    exec (versonFile.read_text(), versionInfo)  # noqa: E211  # black py2.7
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
    return version.public()


def createReleaseBranch(repository: Repository, version: Version) -> Head:
    """
    Create a new release branch.
    """
    branchName = releaseBranchName(version)

    if branchName in repository.heads:
        error(f'Release branch "{branchName}" already exists.', 1)

    print(f'Creating release branch: "{branchName}"')
    return repository.create_head(branchName)


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

    print(
        (
            f"Next steps:\n"
            f" • Commit version updates to release branch: {branch}\n"
            f" • Push the release branch to GitHub\n"
            f" • Open a pull request on GitHub from the release branch\n"
        ),
        end="",
    )


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

    print(f"New release candidate version: {version.public()}")


def publishRelease() -> None:
    """
    Publish the current version.
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

    tagName = releaseTagName(version)

    if tagName in repository.tags:
        tag = repository.tags[tagName]
        if tag.commit != repository.head.ref.commit:
            error(f"Release tag already exists: {tagName}", 1)
    else:
        print("Creating release tag:", tagName)
        tag = repository.create_tag(
            tagName, ref=branch, message=f"Tag release {version.public()}"
        )

    print("Pushing tag to origin:", tag)
    repository.remotes.origin.push(refspec=tag.path)


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
def publish() -> None:
    publishRelease()


if __name__ == "__main__":
    main()
