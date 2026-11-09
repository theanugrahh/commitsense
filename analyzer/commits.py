"""Commit metadata extraction from an open GitPython repository."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterator

from git import Repo, exc

from analyzer.repository import RepositoryError

logger = logging.getLogger(__name__)

DEFAULT_MAX_COMMITS = 10_000
MAX_FILES_PER_COMMIT = 500


def _safe_str(value: object) -> str:
    """Coerce Git-provided text to str, tolerating odd encodings."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


@dataclass(frozen=True)
class CommitRecord:
    """Flat, plain-Python snapshot of one Git commit."""

    sha: str
    short_sha: str
    message: str
    author_name: str
    author_email: str
    committed_at: object  # tz-aware datetime
    is_merge: bool
    parent_count: int
    files_changed: tuple[str, ...]
    num_files: int
    insertions: int
    deletions: int
    total_lines: int


def iter_commits(
    repo: Repo,
    max_commits: int = DEFAULT_MAX_COMMITS,
) -> Iterator[dict]:
    """Yield raw commit dicts from HEAD history (newest first).

    Includes merge commits; their diff stats are unavailable because Git
    does not diff merges by default.
    """
    try:
        items = list(repo.iter_commits(max_count=max_commits))
    except exc.GitCommandError as err:
        raise RepositoryError(
            f"Git error while reading history: {_safe_str(err.stderr).strip() or err}"
        ) from err
    except (exc.GitError, ValueError) as err:
        raise RepositoryError(
            "Unable to walk commit history (empty or corrupted repository)."
        ) from err

    yield from (_extract_one(commit) for commit in items)


def _extract_one(commit) -> dict:
    """Convert a GitPython commit into a dict of safe primitives."""
    files: tuple[str, ...] = ()
    insertions = 0
    deletions = 0
    num_files = 0

    try:
        stats_files = list(commit.stats.files.items())
        num_files = len(stats_files)
        files = tuple(_safe_str(name) for name, _ in stats_files[:MAX_FILES_PER_COMMIT])
        total = commit.stats.total
        insertions = int(total.get("insertions") or 0)
        deletions = int(total.get("deletions") or 0)
    except (exc.GitError, KeyError, TypeError, ValueError):
        # Missing stats for merge commits or odd metadata: degrade gracefully.
        logger.debug("No diff stats for commit %s", getattr(commit, "hexsha", "?"))

    author = getattr(commit, "author", None)
    author_name = _safe_str(getattr(author, "name", "") or "Unknown")
    author_email = _safe_str(getattr(author, "email", "") or "")
    parent_count = len(getattr(commit, "parents", []) or [])

    committed_at = getattr(commit, "committed_datetime", None)
    try:
        committed_at = committed_at.replace(tzinfo=None) if committed_at.tzinfo else committed_at
    except AttributeError:
        committed_at = None

    return {
        "sha": _safe_str(commit.hexsha),
        "short_sha": _safe_str(commit.hexsha)[:8],
        "message": _safe_str(commit.message).strip(),
        "author_name": author_name,
        "author_email": author_email,
        "committed_at": committed_at,
        "is_merge": parent_count > 1,
        "parent_count": parent_count,
        "files_changed": files,
        "num_files": num_files,
        "insertions": insertions,
        "deletions": deletions,
    }


def extract_commits(
    repo: Repo, max_commits: int = DEFAULT_MAX_COMMITS
) -> list[CommitRecord]:
    """Extract commit records into typed CommitRecord objects."""
    records: list[CommitRecord] = []
    for data in iter_commits(repo, max_commits=max_commits):
        data["total_lines"] = data["insertions"] + data["deletions"]
        records.append(CommitRecord(**data))
    return records
