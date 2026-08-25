"""Integration tests: strict index check on ``git_commit`` (Verdict-Carrying).

Exercise :class:`axm_git.tools.commit.GitCommitTool` against *real* temporary
git repositories (no subprocess mocking) to prove the strict-index invariant:
the index must hold ONLY what the commit spec declared.

* pre-staged debris outside the spec is refused *fail-loud*, the index is
  restored to its exact pre-call state, and no commit is written (AC1/AC2);
* the refusal exposes every offending path in the additive
  ``unexpected_staged`` data field (AC4);
* a commit hook that mutates an out-of-spec file is *exempt* — the reported
  ``hook_autofixed_files`` path never trips the check, the retry lands (AC3);
* a clean spec whose index matches it exactly commits normally (AC5).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_git.tools.commit import GitCommitTool

pytestmark = pytest.mark.integration


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a git command in *cwd*."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _init_repo(tmp_path: Path) -> Path:
    """Create a real git repo with identity and an initial commit."""
    _git(["init", "-q", "-b", "main"], tmp_path)
    _git(["config", "user.email", "test@example.com"], tmp_path)
    _git(["config", "user.name", "Test"], tmp_path)
    _git(["config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / "README.md").write_text("init\n")
    _git(["add", "-A"], tmp_path)
    _git(["commit", "-q", "-m", "chore: init"], tmp_path)
    return tmp_path


def _staged(repo: Path) -> set[str]:
    """Return the set of currently staged paths (``git diff --cached``)."""
    result = _git(["diff", "--cached", "--name-only"], repo)
    return {line for line in result.stdout.splitlines() if line.strip()}


def _commit_count(repo: Path) -> int:
    """Return the number of commits reachable from HEAD."""
    return int(_git(["rev-list", "--count", "HEAD"], repo).stdout.strip())


def test_pre_staged_debris_outside_spec_is_refused(tmp_path: Path) -> None:
    """AC1/AC2: debris in the index → fail-loud refusal, index restored, no commit."""
    repo = _init_repo(tmp_path)
    (repo / "debris.py").write_text("junk = 1\n")
    (repo / "wanted.py").write_text("value = 2\n")
    # A third party pre-stages debris the spec never claims.
    _git(["add", "debris.py"], repo)
    pre_call_index = _staged(repo)
    before = _commit_count(repo)

    result = GitCommitTool().execute(
        path=str(repo),
        commits=[{"files": ["wanted.py"], "message": "feat: add wanted"}],
    )

    assert result.success is False
    assert result.error is not None
    assert "debris.py" in result.error
    # No commit was written and the index is back to exactly its pre-call state.
    assert _commit_count(repo) == before
    assert _staged(repo) == pre_call_index == {"debris.py"}


def test_refusal_exposes_offending_paths_in_unexpected_staged(tmp_path: Path) -> None:
    """AC4: the additive ``unexpected_staged`` data field carries the debris path."""
    repo = _init_repo(tmp_path)
    (repo / "debris.py").write_text("junk = 1\n")
    (repo / "wanted.py").write_text("value = 2\n")
    _git(["add", "debris.py"], repo)

    result = GitCommitTool().execute(
        path=str(repo),
        commits=[{"files": ["wanted.py"], "message": "feat: add wanted"}],
    )

    assert result.success is False
    assert result.data is not None
    assert "debris.py" in result.data["unexpected_staged"]


def test_hook_mutating_out_of_spec_file_is_exempt(tmp_path: Path) -> None:
    """AC3: a hook mutating an out-of-spec file → retry lands, path reported."""
    repo = _init_repo(tmp_path)
    # A tracked out-of-spec file the hook will mutate (must be tracked so the
    # mutation surfaces in ``git diff --name-only``).
    (repo / "other.py").write_text("x = 0\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "feat: add other"], repo)

    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text(
        "#!/bin/sh\n"
        'sentinel="$(git rev-parse --git-dir)/autofix-done"\n'
        'if [ ! -f "$sentinel" ]; then\n'
        '  touch "$sentinel"\n'
        '  printf "\\n" >> other.py\n'
        '  echo "files were modified by this hook" >&2\n'
        "  exit 1\n"
        "fi\n"
        "exit 0\n"
    )
    hook.chmod(0o755)

    (repo / "wanted.py").write_text("value = 3\n")
    before = _commit_count(repo)

    result = GitCommitTool().execute(
        path=str(repo),
        commits=[{"files": ["wanted.py"], "message": "feat: add wanted"}],
    )

    assert result.success is True, result.error
    assert result.data is not None
    assert "other.py" in result.data["hook_autofixed_files"]
    assert _commit_count(repo) == before + 1


def test_clean_spec_matching_index_commits_normally(tmp_path: Path) -> None:
    """AC5: an index holding exactly the spec paths commits normally (1 commit)."""
    repo = _init_repo(tmp_path)
    (repo / "a.py").write_text("a = 1\n")
    (repo / "b.py").write_text("b = 2\n")
    # Pre-stage exactly the spec paths (nothing more).
    _git(["add", "a.py", "b.py"], repo)
    before = _commit_count(repo)

    result = GitCommitTool().execute(
        path=str(repo),
        commits=[{"files": ["a.py", "b.py"], "message": "feat: add a and b"}],
    )

    assert result.success is True, result.error
    assert _commit_count(repo) == before + 1
    if result.data is not None:
        assert not result.data.get("unexpected_staged")
