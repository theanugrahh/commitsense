# CommitSense

**Lightweight Git repository analytics and commit quality analysis tool built with Python and Streamlit.**

## Problem Statement

Most developers can answer "how many commits does this repo have?" but struggling teams cannot easily answer harder questions: How often are commit messages vague or empty? Which files churn endlessly? Are commits ballooning in size and becoming hard to review? Existing dashboards answer these questions for hosted platforms (GitHub, GitLab), but for any local clone — including private or offline work — there is no quick per-repository answer.

CommitSense is a local, read-only tool that opens a real Git repository, walks its actual history, and reports honest, rule-based analytics. It never fabricates statistics.

## Features

- **Repository analysis** — validate any local path and analyze real commit history (commits, authors, timestamps, changed files, insertions/deletions, merge commits).
- **Message quality engine** — explainable, rule-based classification of empty, vague ("update", "fix", "stuff"), all-caps and short subjects, plus missing Conventional Commit prefixes. Every flagged commit shows which rule fired.
- **Analytics dashboard** — total commits, contributors, most active contributor, merge commits, and large-commit count at a glance.
- **Interactive charts** — commit activity over time, commit size distribution, message quality donut, most frequently modified files, and contributor ranking (Plotly).
- **Detail tabs** — quality issues, large commits (≥ 20 files or ≥ 800 lines, flagged as reviewability signal — not a security verdict), branches, and practical suggestions.
- **Downloadable report** — full Markdown report of actual computed results.
- **Safe by design** — read-only analysis; no shell commands from user input; no database; no uploads.

## Technology Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| UI | Streamlit |
| Git access | GitPython |
| Data modeling | Pandas dataframes for charts |
| Charts | Plotly |
| Testing | Pytest (real temporary Git repos — no mocks) |

## Screenshots

Rendering the app locally and pasting screenshots is left to the reader; the dashboard consists of a sidebar repository input, a health chip, metric cards, four chart panels, and five detail tabs.

## Installation

```bash
git clone https://github.com/theanugrahh/commitsense.git
cd commitsense

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt    # plus: pip install -r requirements-dev.txt
```

Prerequisite: a Git installation available on your PATH (`git --version`).

## How to Run

```bash
streamlit run app.py
```

Then open `http://localhost:8501`, enter a local repository path (e.g. `/Users/you/projects/my-repo` or `~/projects/my-repo`), and press **Analyze**.

## Example Usage

1. Paste a local Git repository path into the sidebar.
2. Choose how many commits to analyze (100–10,000).
3. Click **Analyze**.
4. Review the scorecard: message quality distribution, large commits, hot files and contributor activity.
5. Open the **Suggestions** tab for concrete improvements.
6. Click **Download analysis report (Markdown)** to save the results.

## Project Architecture

```
app.py                     Streamlit application and page layout
analyzer/
    repository.py          path validation, repo opening, branch reading
    commits.py             commit metadata extraction (records + stats)
    statistics.py          rule-based analytics (contributors, hot files, sizes, timeline)
    quality.py             explainable commit message classification
components/
    charts.py              Plotly chart builders (all dark-themed)
utils/
    reports.py             Markdown report generation
tests/                     Pytest suite with real temporary git repos
.streamlit/config.toml     dark theme configuration
```

Analysis flows in one direction: `repository` → `commits` → (`statistics`, `quality`) → dashboard/report. All pure analysis functions take plain `CommitRecord` objects and dicts, which keeps them testable without Git state.

## Testing Instructions

```bash
pytest
```

The suite (45 tests) builds **real temporary Git repositories** in pytest's tmp directory and exercises the actual Git data path — including empty repositories, invalid paths, merge commits, unicode messages, multi-author histories and large-commit detection.

## Limitations

- Analyzes only the currently checked-out history reachable from `HEAD` (other branches' exclusive commits are not included).
- Merge commits are counted but their diff statistics are omitted (Git does not diff merges by default).
- Initially caps analysis at a chosen maximum (default 1,000 commits) for performance.
- Message quality rules are heuristics with English-language matching; they are opinions made explicit, not ground truth.
- Single-process, local desktop tool — not designed for concurrent multi-user access.

## Future Improvements

- Branch comparison and remote-tracking branch analysis.
- CSV/PDF report formats.
- Per-author quality breakdown.
- Configurable rule thresholds.
- Exporting flagged commits as a machine-readable backlog.

## License

MIT — see [LICENSE](LICENSE).
