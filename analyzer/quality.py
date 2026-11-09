"""Commit message quality classification with explainable rules.

Every verdict carries the rule identifiers that produced it so the UI can
explain *why* a message was flagged.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from analyzer.commits import CommitRecord

# Conventional Commits prefix: type(scope)?: subject
CONVENTIONAL_RE = re.compile(
    r"^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)"
    r"(\([a-zA-Z0-9_./-]+\))?[!:]"
)

# Messages that convey no information. Exact match after lowercasing and
# stripping trailing punctuation/whitespace.
VAGUE_EXACT = {
    "update", "updated", "updates",
    "fix", "fixed", "fixes", "bug fix", "bugfix",
    "changes", "change", "stuff", "things", "misc", "misc changes",
    "wip", "work in progress", "asdf", "asdfgh", "test", "tests",
    "temp", "temporary", "tmp", "commit", "save", "saved",
    "oops", "oopsie", "new", "final", "final version", "final fix",
    "modified", "delete", "deleted", "remove", "various changes",
    "more", "again", "cleanup", "quick fix", "minor fix", "small fix",
    "done", "ok", "okay", "it works", "now works", "fix bug",
    "minor changes", "minor", "small changes", "many changes",
    "latest", "first commit", "initial commit", "init",  # noqa: intrinsic
    "",  # empty message
}

# Subject line shorter than this rarely explains anything (after the
# conventional prefix, if any).
MIN_SUBJECT_LENGTH = 15

# A only-caps message usually means a placeholder.
ALL_CAPS_RE = re.compile(r"^[A-Z0-9\s!.,;:-]{3,}$")


@dataclass
class QualityIssue:
    """One explainable finding about a commit message."""

    rule: str          # stable rule id, e.g. "vague_message"
    detail: str        # human-readable explanation


@dataclass
class QualityAssessment:
    """Per-commit message quality data."""

    sha: str
    short_sha: str
    message: str
    author_name: str
    committed_at: object
    grade: str                     # "good" | "fair" | "poor"
    score: int                     # 0-100 heuristic message score
    issues: list[QualityIssue] = field(default_factory=list)
    is_merge: bool = False

    @property
    def flagged(self) -> bool:
        return self.grade != "good"


def classify_record(record: dict) -> QualityAssessment:
    """Classify one commit-message record (dict form) with rule-based checks."""
    message = (record.get("message") or "").strip()
    subject = message.splitlines()[0] if message else ""
    issues: list[QualityIssue] = []

    lowered_subject = subject.lower().strip().rstrip(".:!-— ")

    # Rule: empty message
    if not message:
        issues.append(QualityIssue("empty_message", "Commit has no message at all."))

    # Rule: vague exact minimal message
    if lowered_subject in VAGUE_EXACT and not CONVENTIONAL_RE.match(subject):
        issues.append(
            QualityIssue(
                "vague_message",
                f'Subject "{subject or "∅"}" conveys no specific change.',
            )
        )

    # Rule: very short subject without a conventional prefix
    effective_subject = re.sub(r"^(feat|fix|chore|docs|refactor|test|ci|perf|build|style|revert)(\([^)]*\))?[:!]\s*", "", subject, flags=re.IGNORECASE)
    if len(effective_subject) < MIN_SUBJECT_LENGTH and not issues:
        issues.append(
            QualityIssue(
                "short_subject",
                f"Subject is only {len(effective_subject)} characters; "
                "explanations should describe what and why.",
            )
        )

    # Rule: placeholder-like all-caps
    if ALL_CAPS_RE.match(subject) and not CONVENTIONAL_RE.match(subject):
        issues.append(QualityIssue("all_caps", "Subject is a shouty/placeholder-looking message."))

    # Rule: missing conventional commit prefix (fair, not "poor" on its own)
    conventional = bool(CONVENTIONAL_RE.match(subject))
    if not conventional:
        issues.append(
            QualityIssue(
                "no_conventional_prefix",
                'No Conventional Commit prefix (e.g. "feat:", "fix:").',
            )
        )

    # Rule: merge commits with the raw default text
    if record.get("is_merge") and re.match(r"^Merge (branch|remote-tracking branch|pull request|\w)", message, flags=re.IGNORECASE):
        issues.append(QualityIssue("default_merge_text", "Auto-generated merge text; a custom message can explain intent."))

    # Grade: poor if a serious issue exists; fair if only prefix missing;
    # good otherwise.
    serious = {"empty_message", "vague_message", "short_subject", "all_caps"}
    if any(i.rule in serious for i in issues):
        grade = "poor"
    elif issues:
        grade = "fair"
    else:
        grade = "good"

    # Score: simple, explainable heuristic.
    score = 100
    deductions = {
        "empty_message": 60,
        "vague_message": 40,
        "short_subject": 25,
        "all_caps": 20,
        "no_conventional_prefix": 10,
        "default_merge_text": 5,
    }
    for issue in issues:
        score -= deductions.get(issue.rule, 0)
    score = max(0, min(100, score))

    return QualityAssessment(
        sha=record.get("sha", ""),
        short_sha=record.get("short_sha", ""),
        message=message,
        author_name=record.get("author_name", "Unknown"),
        committed_at=record.get("committed_at"),
        grade=grade,
        score=score,
        issues=issues,
        is_merge=bool(record.get("is_merge")),
    )


def assess_commit(commit: CommitRecord) -> QualityAssessment:
    """Convenience wrapper accepting a CommitRecord."""
    return classify_record(
        {
            "sha": commit.sha,
            "short_sha": commit.short_sha,
            "message": commit.message,
            "author_name": commit.author_name,
            "committed_at": commit.committed_at,
            "is_merge": commit.is_merge,
        }
    )


def assess_commits(commits: Iterable[CommitRecord]) -> list[QualityAssessment]:
    """Assess every commit message; merge commits are included."""
    return [assess_commit(c) for c in commits]


def quality_summary(assessments: Iterable[QualityAssessment]) -> dict:
    """Aggregate quality grades across commits for dashboard display."""
    assessments = list(assessments)
    counts = {"good": 0, "fair": 0, "poor": 0}
    for a in assessments:
        counts[a.grade] += 1
    total = len(assessments)
    poor_ratio = counts["poor"] / total if total else 0.0

    if total == 0:
        health = "unknown"
    elif poor_ratio <= 0.10:
        health = "healthy"
    elif poor_ratio <= 0.35:
        health = "needs attention"
    else:
        health = "at risk"

    # Rank which specific rules dominate across the history.
    rule_counts: dict[str, int] = {}
    for a in assessments:
        for issue in a.issues:
            rule_counts[issue.rule] = rule_counts.get(issue.rule, 0) + 1

    return {
        "grades": counts,
        "total": total,
        "poor_ratio": poor_ratio,
        "avg_score": (sum(a.score for a in assessments) / total) if total else 0.0,
        "health": health,
        "top_rules": sorted(rule_counts.items(), key=lambda kv: (-kv[1], kv[0])),
    }


SUGGESTIONS = {
    "empty_message": "Always pass -m with a short description: git commit -m \"feat: add X\".",
    "vague_message": "Replace generic subjects with what and why: \"fix: prevent double-submit on login form\".",
    "short_subject": "Aim for at least ~15 characters after the prefix describing the change.",
    "all_caps": "Use normal sentence case; SHOUTING subjects usually mean placeholder text.",
    "no_conventional_prefix": "Adopt Conventional Commits: feat, fix, chore, docs, refactor, test, ci, perf, build, style, revert.",
    "default_merge_text": "Prefer rebase-style merges or write a custom merge message explaining intent.",
}
