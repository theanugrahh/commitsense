"""Statistics engine tests."""

from __future__ import annotations

import pytest
from datetime import date

from analyzer import commits as cm
from analyzer import repository as repo_mod
from analyzer import statistics as sm


def _records(repo_dir):
    return cm.extract_commits(repo_mod.open_repository(str(repo_dir)))


class TestSmallRepo:
    @pytest.fixture(autouse=True)
    def setup(self, sample_repo):
        self.records = _records(sample_repo)

    def test_extraction_counts(self):
        assert self.records is not None

    def test_contributor_summary_counts_by_email(self):
        summary = sm.contributor_summary(self.records)
        assert len(summary) == 1
        entry = next(iter(summary.values()))
        assert entry["commits"] == 5
        assert entry["name"] == "Alice Dev"

    def test_file_modification_counts(self):
        counts = sm.file_change_counts(self.records)
        pairs = dict(counts)
        assert set(pairs) >= {"src/app.py", "README.md", "src/__init__.py"}
        # Sorted descending
        values = [c for _, c in counts]
        assert values == sorted(values, reverse=True)

    def test_headline_numbers(self):
        s = sm.headline_numbers(self.records)
        assert s["total_commits"] == 5
        assert s["merge_commits"] == 0
        assert s["contributors"] == 1
        assert s["total_insertions"] > 0
        assert s["most_active"]["commits"] == 5

    def test_timeline_includes_gap_days(self):
        timeline = sm.commit_timeline(self.records)
        assert len(timeline) >= 1
        dates = [d for d, _ in timeline]
        assert dates == sorted(dates)
        assert all(isinstance(d, date) for d in dates)

    def test_size_distribution_has_buckets(self):
        dist = dict(sm.size_distribution(self.records))
        assert sum(dist.values()) == len([r for r in self.records if not r.is_merge])


class TestMergeRepo:
    @pytest.fixture(autouse=True)
    def setup(self, merge_repo):
        self.records = _records(merge_repo)

    def test_merge_detected_and_excluded_from_size(self):
        s = sm.headline_numbers(self.records)
        assert s["merge_commits"] == 1
        non_merge = [r for r in self.records if not r.is_merge]
        assert s["non_merge_commits"] == len(non_merge)

    def test_large_commit_detection_ignores_merges(self):
        large = [r for r in self.records if sm.is_large_commit(r)]
        merges = [r for r in self.records if r.is_merge]
        assert not any(r.sha in {m.sha for m in merges} for r in large)


class TestMultiAuthorRepo:
    @pytest.fixture(autouse=True)
    def setup(self, multi_author_repo):
        self.records = _records(multi_author_repo)

    def test_same_email_counts_once(self):
        summary = sm.contributor_summary(self.records)
        assert len(summary) == 2
        alice = next(
            e for e in summary.values() if e["email"] == "alice@example.com"
        )
        assert alice["commits"] == 2

    def test_hot_file_is_top_modified(self):
        counts = sm.file_change_counts(self.records)
        assert counts[0][0] == "hot.py"
        assert counts[0][1] == 3

    def test_most_active_metric(self):
        s = sm.headline_numbers(self.records)
        assert s["most_active"]["name"] == "Alice"


class TestLargeCommits:
    def test_threshold_flags_many_files(self):
        record = cm.CommitRecord(
            sha="0" * 40,
            short_sha="0" * 8,
            message="x",
            author_name="A",
            author_email="a@b.c",
            committed_at=None,
            is_merge=False,
            parent_count=1,
            files_changed=tuple(f"f{i}" for i in range(25)),
            num_files=25,
            insertions=10,
            deletions=0,
            total_lines=10,
        )
        assert sm.is_large_commit(record)

    def test_threshold_flags_many_lines(self):
        record = cm.CommitRecord(
            sha="1" * 40,
            short_sha="1" * 8,
            message="x",
            author_name="A",
            author_email="a@b.c",
            committed_at=None,
            is_merge=False,
            parent_count=1,
            files_changed=("one",),
            num_files=1,
            insertions=900,
            deletions=0,
            total_lines=900,
        )
        assert sm.is_large_commit(record)

    def test_small_commit_not_flagged(self):
        record = cm.CommitRecord(
            sha="2" * 40,
            short_sha="2" * 8,
            message="x",
            author_name="A",
            author_email="a@b.c",
            committed_at=None,
            is_merge=False,
            parent_count=1,
            files_changed=("one",),
            num_files=1,
            insertions=5,
            deletions=2,
            total_lines=7,
        )
        assert not sm.is_large_commit(record)


class TestEdgeCases:
    def test_empty_commit_list(self):
        assert sm.headline_numbers([])["total_commits"] == 0
        assert sm.contributor_summary([]) == {}
        assert sm.file_change_counts([]) == []
        assert sm.commit_timeline([]) == []
        assert sm.size_distribution([]) == []

    def test_bucket_label_for_extreme(self):
        assert sm.bucket_for(0) == "Tiny (<= 10 lines)"
        assert sm.bucket_for(10_000_000) == "Very large (> 800 lines)"
