"""Commit quality classification tests."""

from __future__ import annotations

from datetime import datetime

import pytest

from analyzer import quality as q


def _msg(message: str, sha: str = "a" * 40, is_merge: bool = False):
    return {
        "sha": sha,
        "short_sha": sha[:8],
        "message": message,
        "author_name": "Tester",
        "committed_at": datetime(2026, 1, 1),
        "is_merge": is_merge,
    }


class TestClassify:
    def test_good_conventional_message(self):
        a = q.classify_record(_msg("feat: add user authentication service"))
        assert a.grade == "good" and not a.flagged
        assert a.score == 100

    def test_empty_message_is_poor(self):
        a = q.classify_record(_msg(""))
        assert a.grade == "poor"
        rules = {i.rule for i in a.issues}
        assert "empty_message" in rules

    def test_vague_single_word_messages(self):
        for subject in ["update", "fix", "changes", "stuff", "wip", "asdf"]:
            a = q.classify_record(_msg(subject))
            assert a.grade == "poor", subject
            assert any(i.rule == "vague_message" for i in a.issues)

    def test_short_subject(self):
        a = q.classify_record(_msg("fix css"))
        assert a.grade == "poor"
        assert any(i.rule == "short_subject" for i in a.issues)

    def test_all_caps_placeholder(self):
        a = q.classify_record(_msg("ASDF GHJK NOW"))
        assert any(i.rule == "all_caps" for i in a.issues)

    def test_missing_conventional_prefix_is_fair(self):
        a = q.classify_record(_msg("Added a new pagination helper to the list component"))
        assert a.grade == "fair"
        rules = {i.rule for i in a.issues}
        assert rules == {"no_conventional_prefix"}

    def test_conventional_with_scope(self):
        a = q.classify_record(_msg("fix(router): correct double navigation on 404"))
        assert a.grade == "good"

    def test_default_merge_text_detected(self):
        a = q.classify_record(_msg("Merge branch 'feature' into main", is_merge=True))
        rules = {i.rule for i in a.issues}
        assert "default_merge_text" in rules

    def test_score_bounds(self):
        a = q.classify_record(_msg(""))
        assert a.score == 0


class TestSummary:
    def test_quality_summary_shape(self):
        records = [
            q.classify_record(_msg("feat: alpha with full detail", sha="1" * 40)),
            q.classify_record(_msg("update", sha="2" * 40)),
            q.classify_record(_msg("chore: bump dependency patches", sha="3" * 40)),
        ]
        s = q.quality_summary(records)
        assert s["total"] == 3
        assert s["grades"]["poor"] == 1
        assert s["grades"]["good"] == 2
        rules = dict(s["top_rules"])
        assert rules["vague_message"] == 1
        # 1 in 3 messages flagged poor is above the 10% "healthy" ceiling.
        assert s["health"] == "needs attention"

    def test_empty_summary(self):
        s = q.quality_summary([])
        assert s["total"] == 0 and s["health"] == "unknown"

    def test_at_risk_when_many_poor(self):
        records = [q.classify_record(_msg("update", sha=f"{i}" * 40)) for i in range(10)]
        s = q.quality_summary(records)
        assert s["health"] == "at risk"

    def test_suggestions_cover_flagged_rules(self):
        for rule in [
            "empty_message",
            "vague_message",
            "short_subject",
            "no_conventional_prefix",
            "all_caps",
        ]:
            assert rule in q.SUGGESTIONS


class TestRecordIntegration:
    def test_assess_commits_runs_over_real_repo(self, sample_repo):
        from analyzer import commits as cm
        from analyzer import repository as repo_mod

        records = cm.extract_commits(repo_mod.open_repository(str(sample_repo)))
        assessments = q.assess_commits(records)
        assert len(assessments) == len(records)
        vague = [a for a in assessments if "update" in a.message.lower()]
        assert any(a.flagged for a in vague)
