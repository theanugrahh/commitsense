"""Extraction tests against real repositories."""

from __future__ import annotations

import pytest
from git import Repo

from analyzer import commits as commits_mod
from analyzer import repository as repo_mod


def test_valid_repo_opens(sample_repo):
    repo = repo_mod.open_repository(str(sample_repo))
    assert isinstance(repo, Repo)


def test_invalid_path_raises(sample_repo):
    with pytest.raises(repo_mod.RepositoryError):
        repo_mod.open_repository(str(sample_repo / "definitely-not-here"))


def test_not_a_git_dir_raises(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "file.txt").write_text("hello")
    with pytest.raises(repo_mod.RepositoryError, match="not a Git repository"):
        repo_mod.open_repository(str(plain))


def test_empty_path_raises():
    with pytest.raises(repo_mod.RepositoryError, match="enter a repository path"):
        repo_mod.open_repository("   ")


def test_bare_nonexistent_path_message():
    with pytest.raises(repo_mod.RepositoryError, match="does not exist"):
        repo_mod.open_repository("/no/such/place/at/all")


def test_empty_repo_branch_check(empty_repo):
    with pytest.raises(repo_mod.RepositoryError, match="no commits yet"):
        repo_mod.open_repository(str(empty_repo))


def test_extract_commits_basic(sample_repo):
    repo = repo_mod.open_repository(str(sample_repo))
    records = commits_mod.extract_commits(repo)
    assert len(records) == 5
    first = records[0]  # newest first
    assert first.short_sha and len(first.sha) == 40
    assert records[0].message == "refactor: split logging config"
    assert first.author_name == "Alice Dev"
    assert any(r.is_merge is False for r in records)


def test_files_changed_and_stats(sample_repo):
    repo = repo_mod.open_repository(str(sample_repo))
    records = commits_mod.extract_commits(repo)
    by_msg = {r.message: r for r in records}
    refactor = by_msg["refactor: split logging config"]
    assert "src/__init__.py" in refactor.files_changed
    assert refactor.num_files >= 1
    assert refactor.insertions + refactor.deletions == refactor.total_lines


def test_merge_commit_flagged(merge_repo):
    repo = repo_mod.open_repository(str(merge_repo))
    records = commits_mod.extract_commits(repo)
    merges = [r for r in records if r.is_merge]
    assert len(merges) == 1
    assert "Merge branch 'feature'" in merges[0].message


def test_unicode_message_survives_extraction(merge_repo):
    repo = repo_mod.open_repository(str(merge_repo))
    records = commits_mod.extract_commits(repo)
    assert any("✨" in r.message for r in records), (
        "unicode commit message should be extracted without replacement noise"
    )


def test_small_intro_message(sample_repo):
    repo = repo_mod.open_repository(str(sample_repo))
    records = commits_mod.extract_commits(repo)
    assert {r.message for r in records} >= {"update", "fix bug"}
