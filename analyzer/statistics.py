"""Rule-based repository statistics derived from extracted commit records.

Pure functions over lists of CommitRecord so they are trivial to test.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from datetime import date, timedelta

from analyzer.commits import CommitRecord

LARGE_COMMIT_FILE_THRESHOLD = 20
LARGE_COMMIT_LINE_THRESHOLD = 800

SIZE_BUCKETS: tuple[tuple[str, int], ...] = (
    ("Tiny (<= 10 lines)", 10),
    ("Small (<= 50 lines)", 50),
    ("Medium (<= 200 lines)", 200),
    ("Large (<= 800 lines)", 800),
    ("Very large (> 800 lines)", 10**12),
)


def is_large_commit(commit: CommitRecord) -> bool:
    """A commit is 'large' when it touches many files or many lines.

    This is a signal of possible scope creep or missing modular commits —
    it is NOT a security verdict.
    """
    if commit.is_merge:
        return False
    return (
        commit.num_files >= LARGE_COMMIT_FILE_THRESHOLD
        or commit.total_lines >= LARGE_COMMIT_LINE_THRESHOLD
    )


def bucket_for(total_lines: int) -> str:
    """Return the human-readable size bucket for a commit's line total."""
    for label, upper in SIZE_BUCKETS:
        if total_lines <= upper:
            return label
    return SIZE_BUCKETS[-1][0]


def contributor_summary(commits: Iterable[CommitRecord]) -> dict[str, dict]:
    """Aggregate per-author commit counts and line changes.

    Keyed by lowercase email when available, falling back to author name,
    so the same person committed with both name variants is counted once.
    """
    summary: dict[str, dict] = {}
    for c in commits:
        key = (c.author_email or c.author_name or "unknown").strip().lower()
        entry = summary.setdefault(
            key,
            {
                "name": c.author_name or "Unknown",
                "email": c.author_email or "",
                "commits": 0,
                "insertions": 0,
                "deletions": 0,
            },
        )
        entry["commits"] += 1
        entry["insertions"] += c.insertions
        entry["deletions"] += c.deletions
    return summary


def file_change_counts(commits: Iterable[CommitRecord]) -> list[tuple[str, int]]:
    """Return (file, change_count) pairs sorted most-changed first.

    Non-code churn files (lockfiles, generated assets) are still counted,
    but the caller may present them with that context.
    """
    counter: Counter[str] = Counter()
    for c in commits:
        counter.update(c.files_changed)
    return counter.most_common()


def commit_timeline(commits: Iterable[CommitRecord]) -> list[tuple[date, int]]:
    """Daily commit counts, oldest first, including zero-commit gap days."""
    counts: Counter[date] = Counter()
    for c in commits:
        if c.committed_at is not None:
            counts[c.committed_at.date()] += 1
    if not counts:
        return []
    first, last = min(counts), max(counts)
    timeline: list[tuple[date, int]] = []
    current = first
    while current <= last:
        timeline.append((current, counts.get(current, 0)))
        current += timedelta(days=1)
    return timeline


def size_distribution(commits: Iterable[CommitRecord]) -> list[tuple[str, int]]:
    """Group non-merge commits into size buckets."""
    counts: Counter[str] = Counter()
    for c in commits:
        if not c.is_merge:
            counts[bucket_for(c.total_lines)] += 1
    # Preserve bucket order, including empty buckets for a stable chart axis.
    order = {label: idx for idx, (label, _) in enumerate(SIZE_BUCKETS)}
    return sorted(counts.items(), key=lambda item: order.get(item[0], len(order)))


def headline_numbers(commits: Iterable[CommitRecord]) -> dict:
    """Compute the top-level dashboard metrics."""
    commits = list(commits)
    non_merge = [c for c in commits if not c.is_merge]
    merge_count = len(commits) - len(non_merge)

    contributors = contributor_summary(commits)
    most_active = None
    if contributors:
        most_active = max(contributors.values(), key=lambda e: e["commits"])

    file_counts = file_change_counts(commits)

    large = [c for c in non_merge if is_large_commit(c)]

    return {
        "total_commits": len(commits),
        "non_merge_commits": len(non_merge),
        "merge_commits": merge_count,
        "contributors": len(contributors),
        "most_active": most_active,
        "total_insertions": sum(c.insertions for c in commits),
        "total_deletions": sum(c.deletions for c in commits),
        "most_modified_file": file_counts[0] if file_counts else None,
        "large_commits": large,
        "large_commit_count": len(large),
        "avg_files_per_commit": (
            sum(c.num_files for c in non_merge) / len(non_merge) if non_merge else 0.0
        ),
        "first_commit_at": min(
            (c.committed_at for c in commits if c.committed_at is not None),
            default=None,
        ),
        "last_commit_at": max(
            (c.committed_at for c in commits if c.committed_at is not None),
            default=None,
        ),
    }


def run_analysis(commits: list[CommitRecord]) -> dict:
    """Run the full rule-based analysis pipeline once, returning a report dict."""
    return {
        "headline": headline_numbers(commits),
        "contributors": contributor_summary(commits),
        "file_changes": file_change_counts(commits),
        "timeline": commit_timeline(commits),
        "size_distribution": size_distribution(commits),
    }
