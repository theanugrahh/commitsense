"""Local Git repository reader.

Validates directories, detects Git availability, and exposes commit data
from a local repository without executing arbitrary user commands.
"""

from __future__ import annotations

import logging
from pathlib import Path

from git import Repo, exc

logger = logging.getLogger(__name__)


class RepositoryError(Exception):
    """Raised when a path cannot be analyzed as a Git repository."""


class GitNotInstalledError(RepositoryError):
    """Raised when the Git binary is not available on this system."""


def _is_executable_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_mode & 0o111 != 0


def git_available() -> bool:
    """Return True when a Git binary can be located."""
    import shutil

    return shutil.which("git") is not None


def validate_path(raw_path: str) -> Path:
    """Validate a user-supplied directory path.

    Returns the resolved absolute directory. Raises RepositoryError with a
    user-friendly message when the path is missing, unreadable, or not a
    directory. Only reads and inspects the path; never executes commands.
    """
    if not raw_path or not raw_path.strip():
        raise RepositoryError("Please enter a repository path.")

    candidate = Path(raw_path.strip()).expanduser()
    resolved = candidate.resolve()

    if not resolved.exists():
        raise RepositoryError(f"Path does not exist: {resolved}")
    if not resolved.is_dir():
        raise RepositoryError(f"Path is not a directory: {resolved}")

    try:
        list(resolved.iterdir())
    except PermissionError as err:
        raise RepositoryError(f"Permission denied while reading {resolved}") from err

    return resolved


def open_repository(raw_path: str) -> Repo:
    """Open and validate a Git repository at the given path.

    Raises:
        GitNotInstalledError: Git binary is missing.
        RepositoryError: Path invalid, not a repo, or bare/empty repo.
    """
    if not git_available():
        raise GitNotInstalledError(
            "Git is not installed or not on your PATH. "
            "Install Git and try again."
        )

    directory = validate_path(raw_path)

    try:
        repo = Repo(directory)
    except exc.NoSuchPathError as err:
        raise RepositoryError(f"Path does not exist: {directory}") from err
    except exc.InvalidGitRepositoryError as err:
        raise RepositoryError(
            f"{directory} is not a Git repository "
            "(make sure the folder contains a .git directory)."
        ) from err

    try:
        heads = repo.heads
    except (exc.GitError, ValueError) as err:
        raise RepositoryError(
            "Repository metadata could not be read. The repository may be "
            "corrupted."
        ) from err

    if not heads:
        raise RepositoryError(
            "This repository has no commits yet (empty repository)."
        )

    return repo


def read_branches(repo: Repo) -> list[str]:
    """Return local branch names ordered by most recent commit."""
    branches: list[tuple[str, object]] = []
    for head in repo.heads:
        try:
            branches.append((head.name, head.commit))
        except (exc.GitError, ValueError):
            logger.debug("Skipping unreadable branch %s", head.name)
            continue
    branches.sort(key=lambda item: item[1].committed_datetime, reverse=True)
    return [name for name, _ in branches]
