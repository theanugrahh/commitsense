"""Shared pytest fixtures that build real temporary Git repositories.

These create genuine git repos via GitPython so tests exercise the actual
Git data path rather than mocks.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from git import Repo
from git.util import Actor


@pytest.fixture()
def sample_repo(tmp_path: Path) -> Path:
    """A small well-formed repository with mixed quality messages."""
    repo_dir = tmp_path / "sample"
    repo_dir.mkdir()
    repo = Repo.init(repo_dir, initial_branch="main")
    with repo.config_writer() as cw:
        cw.set_value("user", "name", "Alice Dev")
        cw.set_value("user", "email", "alice@example.com")

    files = ["src/__init__.py", "src/app.py", "README.md"]

    scenarios = [
        ("feat: add user service with validation", "src/app.py", "value = 1\n"),
        ("fix: correct timezone handling in scheduler", "src/app.py", "value = 2\n"),
        ("update", "README.md", "readme\n"),
        ("fix bug", "README.md", "readme 2\n"),
        ("refactor: split logging config", "src/__init__.py", "import logging\n"),
    ]
    for i, (msg, fname, content) in enumerate(scenarios):
        p = repo_dir / fname
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        repo.index.add([str(p)])
        dt = f"2026-01-{2+i:02d}T10:{i*5:02d}:00 +0000"
        repo.index.commit(msg, author_date=dt, commit_date=dt)
    # Leave config clean for other tests.
    with repo.config_writer() as cw:
        cw.remove_option("user", "name")
        cw.remove_option("user", "email")
    return repo_dir


@pytest.fixture()
def empty_repo(tmp_path: Path) -> Path:
    """A git repository with zero commits."""
    repo_dir = tmp_path / "empty"
    repo_dir.mkdir()
    Repo.init(repo_dir, initial_branch="main")
    return repo_dir


@pytest.fixture()
def merge_repo(tmp_path: Path) -> Path:
    """Repository containing a merge commit and a unicode message."""
    repo_dir = tmp_path / "mergey"
    repo_dir.mkdir()
    repo = Repo.init(repo_dir, initial_branch="main")
    with repo.config_writer() as cw:
        cw.set_value("user", "name", "Merge Tester")
        cw.set_value("user", "email", "merge@example.com")

    p = repo_dir / "base.txt"
    p.write_text("base\n")
    repo.index.add(["base.txt"])
    repo.index.commit("chore: initial baseline")

    repo.create_head("feature")

    p2 = repo_dir / "main.txt"
    p2.write_text("main work\n")
    repo.index.add(["main.txt"])
    repo.index.commit("feat: main line change")

    repo.heads["feature"].checkout()
    p3 = repo_dir / "feature.txt"
    p3.write_text("feature work ✨\n")
    repo.index.add(["feature.txt"])
    repo.index.commit("feat: add feature with unicode ✨")

    repo.heads["main"].checkout()
    repo.git.merge("feature", "--no-ff", "-m", "Merge branch 'feature' into main")
    return repo_dir


@pytest.fixture()
def multi_author_repo(tmp_path: Path) -> Path:
    """Repository with several contributors and one hot file."""
    repo_dir = tmp_path / "multi"
    repo_dir.mkdir()
    repo = Repo.init(repo_dir, initial_branch="main")

    authors = [
        ("Alice", "alice@example.com"),
        ("Bob", "bob@example.com"),
        ("Alice", "alice@example.com"),  # same person, same email
    ]
    hot = repo_dir / "hot.py"
    for i, (name, email) in enumerate(authors):
        hot.write_text(f"x = {i}\n")
        dt = f"2026-02-{2+i:02d}T10:{i*10:02d}:00 +0000"
        repo.index.add(["hot.py"])
        repo.index.commit(
            f"feat: iteration {i}",
            author=Actor(name, email),
            committer=Actor(name, email),
            author_date=dt,
            commit_date=dt,
        )
    return repo_dir
