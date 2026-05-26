"""Shared pytest fixtures for axm-edit tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _assume_tools_available(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default to tools available; degradation tests override explicitly."""
    monkeypatch.setattr("axm_edit.services.lint._has_ruff", True)
    monkeypatch.setattr("axm_edit.services.lint._has_claude", True)


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory with sample files.

    Layout::

        tmp_path/
        ├── src/
        │   └── foo.py   (5 lines)
        │   └── bar.py   (7 lines)
        └── README.md    (1 line)
    """
    src = tmp_path / "src"
    src.mkdir()

    foo_content = "import os\nimport sys\n\ndef hello():\n    return 42\n"
    bar_content = (
        "import foo\n\ndef greet():\n"
        "    return foo.hello()\n\ndef bye():\n    return 0\n"
    )
    (src / "foo.py").write_text(foo_content)
    (src / "bar.py").write_text(bar_content)
    (tmp_path / "README.md").write_text("# Test Project\n")

    return tmp_path


@pytest.fixture
def git_project(tmp_project: Path) -> Path:
    """Create a temporary git-initialized project."""
    subprocess.run(
        ["git", "init"],
        cwd=tmp_project,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "add", "."],
        cwd=tmp_project,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_project,
        capture_output=True,
        check=True,
        env={
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@test.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@test.com",
            "PATH": "/usr/bin:/usr/local/bin:/opt/homebrew/bin",
        },
    )
    return tmp_project
