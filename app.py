"""CommitSense — Git repository analytics and commit quality analysis.

Run with: streamlit run app.py
"""

from __future__ import annotations

import io
import logging
from datetime import datetime

import streamlit as st

import components.charts as charts
from analyzer import commits as commits_mod
from analyzer import quality as quality_mod
from analyzer import repository as repo_mod
from analyzer import statistics as stats_mod
from utils.reports import build_markdown_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("commitsense")

st.set_page_config(
    page_title="CommitSense",
    page_icon="📊",
    layout="wide",
)

# Central CSS: typography, spacing, cards, badges.
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
    html, body, [class*="css"], .stApp {
        font-family: 'Inter', -apple-system, sans-serif;
    }
    h1, h2, h3 { font-weight: 600; letter-spacing: -0.01em; }
    .block-container { padding-top: 2.2rem; padding-bottom: 3rem; }

    /* Metric cards */
    div[data-testid="stMetric"] {
        background-color: #161b22;
        border: 1px solid rgba(201,209,217,0.10);
        border-radius: 10px;
        padding: 16px 20px;
    }
    div[data-testid="stMetricLabel"] p { color: #8b949e !important; font-size: 0.8rem; }
    div[data-testid="stMetricValue"] { font-size: 1.7rem !important; color: #e6edf3; }

    /* Code font for paths / shas */
    code, pre, .stCodeBlock { font-family: 'JetBrains Mono', monospace; }

    /* Downstream app-wide caption color */
    .app-caption { color: #8b949e; font-size: 0.82rem; }

    /* Grade badges */
    .grade-badge {
        display: inline-block; padding: 2px 10px; border-radius: 999px;
        font-size: 0.75rem; font-weight: 600;
    }
    .badge-good { background: rgba(105,219,124,0.15); color: #69db7c; }
    .badge-fair { background: rgba(255,212,59,0.15); color: #ffd43b; }
    .badge-poor { background: rgba(255,107,123,0.15); color: #ff6b6b; }
    .health-chip {
        display: inline-block; padding: 3px 12px; border-radius: 999px;
        background: rgba(77,171,247,0.12); color: #4dabf7;
        font-size: 0.8rem; font-weight: 600;
    }

    /* Tighten columns holding metrics */
    .metric-row [data-testid="stHorizontalBlock"] { gap: 0.8rem; }
</style>
""",
    unsafe_allow_html=True,
)


def grade_badge(grade: str) -> str:
    label = {"good": "good", "fair": "fair", "poor": "poor"}.get(grade, grade)
    return f'<span class="grade-badge badge-{grade}">{label}</span>'


# ---------- header ----------
header_cols = st.columns([3, 1])
with header_cols[0]:
    st.markdown("## 📊 CommitSense")
    st.caption("Git repository analytics · commit quality · actionable insights")
with header_cols[1]:
    st.caption(datetime.now().strftime("Analysis date: %Y-%m-%d"))

st.divider()

# ---------- sidebar: repository input ----------
with st.sidebar:
    st.markdown("### Repository")
    repo_path_input = st.text_input(
        "Local repository path",
        placeholder="/Users/you/projects/my-repo",
        help="Path to a local Git repository (must contain a .git directory).",
    )
    max_commits = st.select_slider(
        "Maximum commits to analyze",
        options=[100, 500, 1_000, 5_000, 10_000],
        value=1_000,
        help="Limit how deep the history walk goes (protects performance).",
    )
    analyze_btn = st.button("Analyze", type="primary", use_container_width=True)
    st.divider()
    st.caption(
        "CommitSense reads commit history only. It never writes to your "
        "repository and never executes shell commands from your input."
    )

# ---------- session state: run analysis ----------
if "analysis_ready" not in st.session_state:
    st.session_state.analysis_ready = False

if analyze_btn:
    # Reset previous results, then run the pipeline with mapped errors.
    st.session_state.analysis_ready = False
    with st.spinner("Analyzing repository…"):
        repo = None
        branches: list[str] = []
        try:
            repo = repo_mod.open_repository(repo_path_input)
            branches = repo_mod.read_branches(repo)
            raw_commits = commits_mod.extract_commits(repo, max_commits=max_commits)
            analysis = stats_mod.run_analysis(raw_commits)
            assessments = quality_mod.assess_commits(raw_commits)
            quality = quality_mod.quality_summary(assessments)
        except repo_mod.GitNotInstalledError as err:
            st.error(f"**Git not available** — {err}")
            st.session_state.analysis_ready = False
        except repo_mod.RepositoryError as err:
            st.error(f"**Cannot analyze repository** — {err}")
            st.session_state.analysis_ready = False
        except Exception as exc:  # noqa: BLE001 — keep the UI from leaking traces
            logger.exception("Unexpected analysis failure")
            st.error(
                "**Unexpected analysis failure.** The repository metadata could "
                "not be processed. Check the terminal log for details."
            )
            st.session_state.analysis_ready = False
        else:
            # Commit the successful run to session state.
            st.session_state.analysis_ready = True
            st.session_state.analysis = analysis
            st.session_state.quality = quality
            st.session_state.assessments = assessments
            st.session_state.branches = branches
            st.session_state.repo_path = repo_path_input.strip()

# ---------- dashboard render ----------
if not st.session_state.analysis_ready:
    # Landing state with explainable help.
    st.markdown(
        """
        <div style="border:1px solid rgba(201,209,217,0.12); background:#161b22;
             border-radius:12px; padding:28px 32px; margin-top:4px;">
          <h3 style="margin-top:0;">Analyze any local Git repository</h3>
          <p style="color:#8b949e; max-width:640px;">
            Enter a repository path in the sidebar and press <b>Analyze</b>.
            CommitSense inspects real commit history — message quality, commit
            sizes, hot files, contributors and activity timeline — using
            explainable rules. It never fabricates statistics.
          </p>
          <p style="color:#8b949e; max-width:640px;">Examples:</p>
          <code style="font-size:0.85rem;">/Users/you/projects/my-repo</code>
          &nbsp;·&nbsp;
          <code style="font-size:0.85rem;">~/projects/my-repo</code>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

# Always render from this run's stored values (never fabricated).
analysis = st.session_state.analysis
quality = st.session_state.quality
assessments = st.session_state.assessments
branches = st.session_state.branches
headline = analysis["headline"]

# ---------- headline metrics ----------
st.markdown(
    f'<span class="health-chip">Repository health: {quality["health"]}</span>',
    unsafe_allow_html=True,
)
st.write("")

mcols = st.columns(5)
mcols[0].metric("Total commits", f"{headline['total_commits']:,}")
mcols[1].metric("Contributors", headline["contributors"])
mcols[2].metric(
    "Most active",
    (headline["most_active"]["name"] if headline["most_active"] else "—"),
    help="Author with the most commits (by email identity)." if headline["most_active"] else None,
)
mcols[3].metric(
    "Merge commits",
    f"{headline['merge_commits']:,}",
    help=f"{headline['non_merge_commits']:,} non-merge commits analyzed for stats.",
)
mcols[4].metric(
    "Large commits",
    f"{headline['large_commit_count']:,}",
    help="Commits touching ≥ 20 files or ≥ 800 lines (not security verdicts).",
)

st.write("")

# ---------- charts row 1 ----------
c1, c2 = st.columns([3, 2])
with c1:
    st.markdown("##### Commit activity over time")
    if analysis["timeline"]:
        st.plotly_chart(charts.timeline_chart(analysis["timeline"]), use_container_width=True)
    else:
        st.info("No dated commits available for a timeline.")
with c2:
    st.markdown("##### Message quality")
    if quality["total"] > 0:
        st.plotly_chart(charts.quality_donut(quality["grades"]), use_container_width=True)
        st.markdown(
            f'<span class="app-caption">Average message score: '
            f'{quality["avg_score"]:.0f}/100</span>',
            unsafe_allow_html=True,
        )
    else:
        st.info("No commits to assess.")

st.write("")

# ---------- charts row 2 ----------
c3, c4 = st.columns(2)
with c3:
    st.markdown("##### Commit size distribution")
    if analysis["size_distribution"]:
        st.plotly_chart(
            charts.size_distribution_chart(analysis["size_distribution"]),
            use_container_width=True,
        )
    else:
        st.info("No non-merge commits with size data.")
with c4:
    st.markdown("##### Most frequently modified files")
    if analysis["file_changes"]:
        st.plotly_chart(
            charts.top_files_chart(analysis["file_changes"]),
            use_container_width=True,
        )
    else:
        st.info("No file change history available.")

st.write("")

# ---------- tabbed detail section ----------
tabs = st.tabs(
    ["Contributors", "Quality issues", "Large commits", "Branches", "Suggestions"]
)

with tabs[0]:
    if analysis["contributors"]:
        st.plotly_chart(
            charts.contributors_chart(analysis["contributors"]),
            use_container_width=True,
        )
        ranked = sorted(analysis["contributors"].values(), key=lambda e: e["commits"], reverse=True)
        st.dataframe(
            {
                "Author": [e["name"] for e in ranked],
                "Email": [e["email"] or "—" for e in ranked],
                "Commits": [e["commits"] for e in ranked],
                "Lines added": [e["insertions"] for e in ranked],
                "Lines removed": [e["deletions"] for e in ranked],
            },
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No contributor data.")

with tabs[1]:
    flagged = [a for a in assessments if a.flagged]
    st.markdown(
        f'<span class="app-caption">{len(flagged)} of {len(assessments)} '
        "commit messages flagged. Explanations include the rule that fired."
        "</span>",
        unsafe_allow_html=True,
    )
    if flagged:
        from datetime import timezone

        rows = []
        for a in flagged[:50]:
            for issue in a.issues[:1]:  # primary issue per row
                rows.append(
                    {
                        "Commit": a.short_sha,
                        "When": (a.committed_at.strftime("%Y-%m-%d") if a.committed_at else "—"),
                        "Author": a.author_name,
                        "Subject": (a.message.splitlines()[0][:70] if a.message else "(no message)"),
                        f"Grade ({a.grade})": issue.detail,
                        "Rule": issue.rule,
                    }
                )
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.success("Every analyzed commit message follows good practices.")

with tabs[2]:
    st.markdown(
        '<span class="app-caption">Large commits are a reviewability signal, '
        "not a security verdict. Thresholds: ≥ 20 files or ≥ 800 changed "
        "lines.</span>",
        unsafe_allow_html=True,
    )
    if headline["large_commits"]:
        rows = [
            {
                "Commit": c.short_sha,
                "When": (c.committed_at.strftime("%Y-%m-%d") if c.committed_at else "—"),
                "Author": c.author_name,
                "Files": c.num_files,
                "±Lines": c.total_lines,
                "Subject": (c.message.splitlines()[0][:70] if c.message else "(no message)"),
            }
            for c in headline["large_commits"][:100]
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.success("No unusually large commits detected.")

with tabs[3]:
    if branches:
        st.dataframe(
            {"Branch": branches},
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No branches could be listed.")

with tabs[4]:
    st.markdown("#### Practical suggestions")
    bullets = []
    for rule, count in quality["top_rules"][:6]:
        s = quality_mod.SUGGESTIONS.get(rule)
        if s:
            bullets.append(f"- **{rule.replace('_', ' ').title()}** ({count} commits): {s}")
    if headline["large_commit_count"]:
        bullets.append(
            f"- **Large commits ({headline['large_commit_count']}):** split "
            "them into smaller, reviewable commits — feature work, fixes and "
            "refactors should land separately."
        )
    if not bullets:
        bullets.append("- History looks clean. Keep writing specific messages and small commits.")
    for b in bullets:
        st.markdown(b)

st.divider()

# ---------- report download ----------
report_md = build_markdown_report(
    analysis, quality, st.session_state.repo_path, branches
)
st.download_button(
    "⬇ Download analysis report (Markdown)",
    data=io.BytesIO(report_md.encode("utf-8")),
    file_name=f"commitsense-report-{datetime.now():%Y%m%d}.md",
    mime="text/markdown",
    use_container_width=True,
)
