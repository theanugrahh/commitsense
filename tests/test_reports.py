"""Report generation tests: must contain actual computed numbers."""

from __future__ import annotations

from analyzer import commits as cm
from analyzer import quality as q
from analyzer import repository as rm
from analyzer import statistics as sm
from utils.reports import build_markdown_report


def test_report_contains_actual_data(sample_repo):
    repo = rm.open_repository(str(sample_repo))
    branches = rm.read_branches(repo)
    records = cm.extract_commits(repo)
    analysis = sm.run_analysis(records)
    quality = q.quality_summary(q.assess_commits(records))

    report = build_markdown_report(analysis, quality, str(sample_repo), branches)

    # Headline numbers that actually came from the analysis:
    assert f"**Total commits:** {len(records)}" in report
    assert "Alice Dev" in report or "Alice" in report
    assert "src/app.py" in report  # actually modified file
    assert "Commit message quality" in report
    assert "Suggestions" in report
    assert "Large commits" in report or "No unusually large commits" in report


def test_report_flags_vague_messages(sample_repo):
    repo = rm.open_repository(str(sample_repo))
    records = cm.extract_commits(repo)
    quality = q.quality_summary(q.assess_commits(records))
    analysis = sm.run_analysis(records)
    report = build_markdown_report(analysis, quality, "/p", [])
    assert "vague_message" in report


def test_report_on_empty_analysis():
    from analyzer.quality import SUGGESTIONS

    analysis = sm.run_analysis([])
    quality = q.quality_summary([])
    report = build_markdown_report(analysis, quality, "/empty", [])
    assert "Total commits:** 0" in report
    assert "No contributor data" in report
    assert SUGGESTIONS is not None  # sanity


def test_branches_listed(sample_repo):
    repo = rm.open_repository(str(sample_repo))
    branches = rm.read_branches(repo)
    assert "main" in branches
