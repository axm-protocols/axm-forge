"""Integration tests: ``hook_autofixed_files`` on the success path.

Exercise :class:`axm_git.tools.commit.GitCommitTool` against a *real* git
repo and a *real* ``pre-commit`` hook (no subprocess mocking) to prove the
Verdict-Carrying Patch invariant (AC1/AC2/AC3):

* an autofix hook that mutates a staged file, re-stages, and lands the commit
  surfaces the mutated path in ``data["hook_autofixed_files"]`` while still
  reporting ``success=True``;
* a clean commit (no mutating hook) always reports an empty list, never
  ``None``;
* the 47ca9413 autofix-retry flow still lands a commit on HEAD.

The ``commit_repo`` / ``install_hook`` fixtures live in this package's
``tests/integration/conftest.py``. The ``autofix`` hook appends a newline to
``fix_me.py`` and fails once with the canonical marker, then (sentinel-guarded)
accepts the retried commit.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from axm_git.tools.commit import GitCommitTool

pytestmark = pytest.mark.integration


def _head_subject(repo: Path) -> str:
    """Return the subject line of the current HEAD commit."""
    return subprocess.run(
        ["git", "log", "-1", "--format=%s"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_real_hook_mutation_is_reported(
    install_hook: Callable[[str], Path],
) -> None:
    """AC1/AC3: a hook mutating a staged file names it; the commit still lands."""
    repo = install_hook("autofix")
    (repo / "fix_me.py").write_text("value = 1\n")

    result = GitCommitTool().execute(
        path=str(repo),
        commits=[{"files": ["fix_me.py"], "message": "feat: fix_me"}],
    )

    assert result.success is True, result.error
    assert result.data is not None
    assert result.data["hook_autofixed_files"] == ["fix_me.py"]
    assert _head_subject(repo) == "feat: fix_me"


def test_no_mutation_yields_empty_field(
    install_hook: Callable[[str], Path],
) -> None:
    """AC2/AC3: a non-mutating (green) hook leaves the field an empty list."""
    repo = install_hook("green")
    (repo / "clean.py").write_text("x = 2\n")

    result = GitCommitTool().execute(
        path=str(repo),
        commits=[{"files": ["clean.py"], "message": "feat: clean"}],
    )

    assert result.success is True, result.error
    assert result.data is not None
    assert result.data["hook_autofixed_files"] == []


def test_existing_autofix_retry_still_lands_a_commit(
    install_hook: Callable[[str], Path],
) -> None:
    """AC3/AC6: the 47ca9413 re-stage + retry-once flow still creates a commit."""
    repo = install_hook("autofix")
    (repo / "fix_me.py").write_text("value = 3\n")

    before = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    result = GitCommitTool().execute(
        path=str(repo),
        commits=[{"files": ["fix_me.py"], "message": "feat: retry lands"}],
    )

    assert result.success is True, result.error
    after = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert after != before
    assert _head_subject(repo) == "feat: retry lands"
