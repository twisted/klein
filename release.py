from pathlib import Path
from subprocess import CalledProcessError, run
from sys import exit, stderr
from typing import Any, Dict, NoReturn, Optional, Sequence

from git import Repo as Repository
from git.refs.head import Head

from incremental import Version


def warning(message: str) -> None:
    print(f"WARNING: {message}", file=stderr)


def error(message: str, exitStatus: int) -> NoReturn:
    print(f"ERROR: {message}", file=stderr)
    exit(exitStatus)


def spawn(args: Sequence[str]) -> None:
    run(args, capture_output=True, check=True)


def currentVersion() -> Version:
    versionInfo: Dict[str, Any] = {}
    versonFile = Path(__file__).parent / "src" / "klein" / "_version.py"
    exec (versonFile.read_text(), versionInfo)  # noqa: E211  # black py2.7
    return versionInfo["__version__"]


def incrementVersion(candidate: bool) -> None:
    # Incremental doesn't have an API to do this, so we have to run a
    # subprocess. Boo.
    args = ["python", "-m", "incremental.update", "klein"]
    if candidate:
        args.append("--rc")
    try:
        spawn(args)
    except CalledProcessError as e:
        error(f"command {e.cmd} failed: {e.stderr}", 1)


def releaseBranchName(version: Version) -> str:
    return f"release-{version.major}.{version.minor}"


def releaseBranch(repository: Repository, version: Version) -> Optional[Head]:
    branchName = releaseBranchName(version)

    if branchName in repository.heads:
        return repository.heads[branchName]

    return None


def createReleaseBranch(repository: Repository, version: Version) -> Head:
    branchName = releaseBranchName(version)

    if branchName in repository.heads:
        error(f'Release branch "{branchName}" already exists.', 1)

    print(f'Creating release branch: "{branchName}"')
    return repository.create_head(branchName)


def startRelease() -> None:
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

    print(f"New release candidate version: {version}")

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
    repository = Repository()

    if repository.is_dirty():
        warning("working copy is dirty")

    version = currentVersion()

    if version.release_candidate is None:
        error(f"current version is not a release candidate: {version}", 1)

    incrementVersion(candidate=True)
    version = currentVersion()

    print(f"New release candidate version: {version}")

    branch = releaseBranch(repository, version)

    if repository.head.ref != branch:
        error(
            f'working copy is on branch "{repository.head.ref}", '
            f'not release branch "{branch}"',
            1,
        )


def main(argv: Sequence[str]) -> None:
    def invalidArguments() -> NoReturn:
        error(f"invalid arguments: {argv}", 64)

    if len(argv) != 1:
        invalidArguments()

    subcommand = argv[0]

    if subcommand == "start":
        startRelease()
    elif subcommand == "bump":
        bumpRelease()
    else:
        invalidArguments()


if __name__ == "__main__":
    from sys import argv

    main(argv[1:])
