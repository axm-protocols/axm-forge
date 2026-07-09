"""Unit tests for GitCommitTool."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from axm_git.tools.commit import GitCommitTool


def _ok(stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["git"],
        returncode=0,
        stdout=stdout,
        stderr=stderr,
    )


def _fail(stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["git"],
        returncode=1,
        stdout=stdout,
        stderr=stderr,
    )


class TestGitCommitTool:
    """Test GitCommitTool behavior."""

    def test_name(self) -> None:
        tool = GitCommitTool()
        assert tool.name == "git_commit"

    def test_no_commits_provided(self) -> None:
        result = GitCommitTool().execute(path="/tmp/test", commits=[])
        assert not result.success
        assert "No commits" in (result.error or "")

    @patch("axm_git.tools.commit.find_git_root", return_value=Path("/tmp/test"))
    @patch("axm_git.tools.commit.stage_spec_files", return_value=None)
    @patch("axm_git.tools.commit.run_git")
    def test_single_commit_success(
        self, mock_git: MagicMock, _mock_stage: MagicMock, _mock_root: MagicMock
    ) -> None:
        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "add":
                return _ok()
            if args[0] == "commit":
                return _ok()
            if args[0] == "log":
                return _ok("abc1234")
            return _ok()

        mock_git.side_effect = _side_effect
        result = GitCommitTool().execute(
            path="/tmp/test",
            commits=[{"files": ["src/foo.py"], "message": "fix: bug"}],
        )
        assert result.success
        assert result.data["total"] == 1
        assert result.data["results"][0]["sha"] == "abc1234"

    @patch("axm_git.tools.commit.find_git_root", return_value=Path("/tmp/test"))
    @patch("axm_git.tools.commit.stage_spec_files", return_value=None)
    @patch("axm_git.tools.commit.run_git")
    def test_batch_commits(
        self, mock_git: MagicMock, _mock_stage: MagicMock, _mock_root: MagicMock
    ) -> None:
        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "add":
                return _ok()
            if args[0] == "commit":
                return _ok()
            if args[0] == "log":
                return _ok("abc1234")
            return _ok()

        mock_git.side_effect = _side_effect
        result = GitCommitTool().execute(
            path="/tmp/test",
            commits=[
                {"files": ["a.py"], "message": "fix: a"},
                {"files": ["b.py"], "message": "feat: b"},
                {"files": ["c.py"], "message": "docs: c"},
            ],
        )
        assert result.success
        assert result.data["total"] == 3
        assert result.data["succeeded"] == 3

    @patch("axm_git.tools.commit.find_git_root", return_value=Path("/tmp/test"))
    @patch("axm_git.tools.commit.stage_spec_files", return_value=None)
    @patch("axm_git.tools.commit.run_git")
    def test_precommit_failure_stops_batch(
        self, mock_git: MagicMock, _mock_stage: MagicMock, _mock_root: MagicMock
    ) -> None:
        commit_count = 0

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            nonlocal commit_count
            if args[0] == "add":
                return _ok()
            if args[0] == "commit":
                commit_count += 1
                if commit_count == 2:
                    return _fail(stderr="mypy error")
                return _ok()
            if args[0] == "log":
                return _ok("abc1234")
            return _ok()

        mock_git.side_effect = _side_effect
        result = GitCommitTool().execute(
            path="/tmp/test",
            commits=[
                {"files": ["a.py"], "message": "fix: a"},
                {"files": ["b.py"], "message": "feat: b"},
            ],
        )
        assert not result.success
        assert result.data["succeeded"] == 1
        assert result.data["failed_commit"]["index"] == 2

    @patch("axm_git.tools.commit.run_git")
    def test_empty_files_error(self, mock_git: MagicMock) -> None:
        mock_git.return_value = _ok()
        result = GitCommitTool().execute(
            path="/tmp/test",
            commits=[{"files": [], "message": "fix: x"}],
        )
        assert not result.success
        assert "empty files" in (result.error or "")

    @patch("axm_git.tools.commit.run_git")
    def test_empty_message_error(self, mock_git: MagicMock) -> None:
        mock_git.return_value = _ok()
        result = GitCommitTool().execute(
            path="/tmp/test",
            commits=[{"files": ["a.py"], "message": ""}],
        )
        assert not result.success
        assert "empty message" in (result.error or "")

    @patch("axm_git.tools.commit.find_git_root", return_value=Path("/tmp/test"))
    @patch(
        "axm_git.tools.commit.stage_spec_files",
        return_value="files not found: 'x.py'",
    )
    @patch("axm_git.tools.commit.run_git")
    def test_git_add_failure(
        self, mock_git: MagicMock, _mock_stage: MagicMock, _mock_root: MagicMock
    ) -> None:
        mock_git.return_value = _ok()
        result = GitCommitTool().execute(
            path="/tmp/test",
            commits=[{"files": ["x.py"], "message": "fix: x"}],
        )
        assert not result.success
        assert "git add failed" in (result.error or "")

    @patch("axm_git.tools.commit.find_git_root", return_value=Path("/tmp/test"))
    @patch("axm_git.tools.commit.stage_spec_files", return_value=None)
    @patch("axm_git.tools.commit.run_git")
    def test_commit_with_body(
        self, mock_git: MagicMock, _mock_stage: MagicMock, _mock_root: MagicMock
    ) -> None:
        """Commit with body adds second -m flag."""

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "commit":
                m_count = args.count("-m")
                assert m_count == 2
                return _ok()
            if args[0] == "log":
                return _ok("abc1234")
            return _ok()

        mock_git.side_effect = _side_effect
        result = GitCommitTool().execute(
            path="/tmp/test",
            commits=[
                {
                    "files": ["a.py"],
                    "message": "feat: api",
                    "body": "Detailed explanation",
                }
            ],
        )
        assert result.success

    # ── Bug fix tests ──────────────────────────────────────────────

    @patch("axm_git.tools.commit.find_git_root", return_value=Path("/tmp/test"))
    @patch("axm_git.tools.commit.stage_spec_files", return_value=None)
    @patch("axm_git.tools.commit.run_git")
    def test_staging_routes_through_smart_resolver(
        self, mock_git: MagicMock, mock_stage: MagicMock, mock_root: MagicMock
    ) -> None:
        """AC2/AC6: staging goes through the subdir-aware ``stage_spec_files``.

        The naive ``git add -A`` helper was removed; the tool now resolves the
        git root and delegates staging to the promoted resolver, passing the
        given *path* as the working-dir fallback.
        """

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "commit":
                return _ok()
            if args[0] == "log":
                return _ok("abc1234")
            return _ok()

        mock_git.side_effect = _side_effect
        GitCommitTool().execute(
            path="/tmp/test",
            commits=[{"files": ["a.py"], "message": "fix: a"}],
        )
        mock_root.assert_called_once()
        mock_stage.assert_called_once()
        stage_args, stage_kwargs = mock_stage.call_args
        assert stage_args[0] == ["a.py"]
        assert (
            Path(stage_kwargs["working_dir"]).resolve() == Path("/tmp/test").resolve()
        )
        # No raw ``git add`` is issued by the tool any more.
        add_calls = [c for c in mock_git.call_args_list if c[0][0][0] == "add"]
        assert add_calls == []

    @patch("axm_git.tools.commit.find_git_root", return_value=Path("/tmp/test"))
    @patch("axm_git.tools.commit.stage_spec_files", return_value=None)
    def test_auto_retry_on_ruff_fix(
        self, _mock_stage: MagicMock, _mock_root: MagicMock
    ) -> None:
        """When pre-commit auto-fixes, re-stage and retry once.

        The autofix-retry plumbing now lives in the shared core helper, so
        the first commit runs via the tool-module ``run_git`` and the
        retried commit (plus its ``git diff --name-only`` capture) via the
        core helper's ``run_git``.  Bind ONE shared mock to both names so the
        retry assertion (commit_count == 2) holds across the boundary.
        """
        commit_count = 0

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            nonlocal commit_count
            if args[0] == "add":
                return _ok()
            if args[0] == "commit":
                commit_count += 1
                if commit_count == 1:
                    return _fail(stdout="files were modified by this hook")
                return _ok()  # retry succeeds
            if args[0] == "log":
                return _ok("abc1234")
            return _ok()

        mock_git = MagicMock(side_effect=_side_effect)
        with (
            patch("axm_git.tools.commit.run_git", new=mock_git),
            patch("axm_git.core.commit_spec.run_git", new=mock_git),
            patch("axm_git.core.commit_spec.stage_spec_files", return_value=None),
        ):
            result = GitCommitTool().execute(
                path="/tmp/test",
                commits=[{"files": ["a.py"], "message": "fix: a"}],
            )
        assert result.success
        assert result.data["results"][0]["retried"] is True
        assert commit_count == 2

    @patch("axm_git.tools.commit.find_git_root", return_value=Path("/tmp/test"))
    @patch("axm_git.tools.commit.stage_spec_files", return_value=None)
    def test_auto_retry_fails_twice(
        self, _mock_stage: MagicMock, _mock_root: MagicMock
    ) -> None:
        """When retry also fails, report error with retried=True.

        The retry (re-stage + second commit + ``git diff --name-only``
        capture) runs through the shared core helper, so bind ONE mock to
        both the tool and core ``run_git`` names.
        """

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "add":
                return _ok()
            if args[0] == "commit":
                return _fail(stdout="files were modified by this hook")
            if args[0] == "diff":
                return _ok("a.py\n")
            return _ok()

        mock_git = MagicMock(side_effect=_side_effect)
        with (
            patch("axm_git.tools.commit.run_git", new=mock_git),
            patch("axm_git.core.commit_spec.run_git", new=mock_git),
            patch("axm_git.core.commit_spec.stage_spec_files", return_value=None),
        ):
            result = GitCommitTool().execute(
                path="/tmp/test",
                commits=[{"files": ["a.py"], "message": "fix: a"}],
            )
        assert not result.success
        assert result.data["failed_commit"]["retried"] is True
        assert "a.py" in result.data["failed_commit"]["auto_fixed_files"]


class TestScopedIndexRestore:
    """AC1/AC2/AC3/AC4: scoped index restoration on a definitive hook refusal."""

    @patch("axm_git.tools.commit.find_git_root", return_value=Path("/tmp/test"))
    @patch("axm_git.tools.commit.stage_spec_files", return_value=None)
    @patch("axm_git.tools.commit.reset_paths")
    @patch("axm_git.tools.commit._snapshot_staged")
    @patch("axm_git.tools.commit.run_git")
    def test_definitive_failure_scoped_resets_only_op_paths(
        self,
        mock_git: MagicMock,
        mock_snapshot: MagicMock,
        mock_reset: MagicMock,
        _mock_stage: MagicMock,
        _mock_root: MagicMock,
    ) -> None:
        """AC1/AC2/AC4: reset unstages exactly the op-staged delta.

        ``third.py`` was staged by a third party before the call — it is in the
        pre-snapshot, so it is excluded from the recorded delta and never reset.
        """
        # before staging → after staging: op introduced only ``a.py``.
        mock_snapshot.side_effect = [{"third.py"}, {"third.py", "a.py"}]

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "commit":
                return _fail(stderr="mypy error")  # definitive refusal, no autofix
            return _ok()

        mock_git.side_effect = _side_effect
        result = GitCommitTool().execute(
            path="/tmp/test",
            commits=[{"files": ["a.py"], "message": "fix: a"}],
        )
        assert not result.success
        mock_reset.assert_called_once_with(["a.py"], Path("/tmp/test"))
        assert "index restored" in (result.error or "")
        failed = result.data["failed_commit"]
        assert failed["index_restored"] is True
        assert failed["restored_paths"] == ["a.py"]
        assert "index restored" in (result.text or "")

    @patch("axm_git.tools.commit.find_git_root", return_value=Path("/tmp/test"))
    @patch("axm_git.tools.commit.stage_spec_files", return_value=None)
    @patch("axm_git.tools.commit.reset_paths")
    @patch("axm_git.tools.commit._snapshot_staged")
    @patch("axm_git.tools.commit.run_git")
    def test_nominal_success_never_restores(
        self,
        mock_git: MagicMock,
        mock_snapshot: MagicMock,
        mock_reset: MagicMock,
        _mock_stage: MagicMock,
        _mock_root: MagicMock,
    ) -> None:
        """AC3: the green path stages, commits, and never touches the index."""
        mock_snapshot.side_effect = [set(), {"a.py"}]

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "log":
                return _ok("abc1234")
            return _ok()

        mock_git.side_effect = _side_effect
        result = GitCommitTool().execute(
            path="/tmp/test",
            commits=[{"files": ["a.py"], "message": "fix: a"}],
        )
        assert result.success
        mock_reset.assert_not_called()
        assert "index restored" not in (result.text or "")

    @patch("axm_git.tools.commit.find_git_root", return_value=Path("/tmp/test"))
    @patch("axm_git.tools.commit.stage_spec_files", return_value=None)
    @patch("axm_git.tools.commit.reset_paths")
    def test_autofix_retry_success_never_restores(
        self,
        mock_reset: MagicMock,
        _mock_stage: MagicMock,
        _mock_root: MagicMock,
    ) -> None:
        """AC3: the auto-fix-then-green retry path must NOT trigger a restore."""

        commit_count = 0

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            nonlocal commit_count
            if args[0] == "commit":
                commit_count += 1
                if commit_count == 1:
                    return _fail(stdout="files were modified by this hook")
                return _ok()  # retry succeeds
            if args[0] == "log":
                return _ok("abc1234")
            return _ok()

        mock_git = MagicMock(side_effect=_side_effect)
        with (
            patch("axm_git.tools.commit.run_git", new=mock_git),
            patch("axm_git.core.commit_spec.run_git", new=mock_git),
            patch("axm_git.core.commit_spec.stage_spec_files", return_value=None),
        ):
            result = GitCommitTool().execute(
                path="/tmp/test",
                commits=[{"files": ["a.py"], "message": "fix: a"}],
            )
        assert result.success
        mock_reset.assert_not_called()


class TestConventionalCommitValidation:
    """Conventional Commit format validation in the commit path."""

    @staticmethod
    def _side_effect(
        args: list[str], cwd: Any, **kw: Any
    ) -> subprocess.CompletedProcess[str]:
        if args[0] == "log":
            return _ok("abc1234")
        return _ok()

    @patch("axm_git.tools.commit.find_git_root", return_value=Path("/tmp/test"))
    @patch("axm_git.tools.commit.stage_spec_files", return_value=None)
    @patch("axm_git.tools.commit.run_git")
    def test_non_conventional_message_warns(
        self,
        mock_git: MagicMock,
        _mock_stage: MagicMock,
        _mock_root: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """AC1, AC4: a non-conventional message warns but the commit proceeds."""
        mock_git.side_effect = self._side_effect
        with caplog.at_level(logging.WARNING):
            result = GitCommitTool().execute(
                path="/tmp/test",
                commits=[{"files": ["a.py"], "message": "wip stuff"}],
            )
        assert result.success is True
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("wip stuff" in r.getMessage() for r in warnings)

    @pytest.mark.parametrize(
        "message",
        [
            pytest.param("feat(core): add x", id="scoped_conventional"),
            pytest.param("feat!: drop y", id="breaking_marker"),
        ],
    )
    @patch("axm_git.tools.commit.find_git_root", return_value=Path("/tmp/test"))
    @patch("axm_git.tools.commit.stage_spec_files", return_value=None)
    @patch("axm_git.tools.commit.run_git")
    def test_conventional_message_no_warning(
        self,
        mock_git: MagicMock,
        _mock_stage: MagicMock,
        _mock_root: MagicMock,
        caplog: pytest.LogCaptureFixture,
        message: str,
    ) -> None:
        """AC2, AC3: valid conventional messages (incl. breaking ``!``).

        Emit no warning.
        """
        mock_git.side_effect = self._side_effect
        with caplog.at_level(logging.WARNING):
            result = GitCommitTool().execute(
                path="/tmp/test",
                commits=[{"files": ["a.py"], "message": message}],
            )
        assert result.success is True
        assert not any(message in r.getMessage() for r in caplog.records)

    @patch("axm_git.tools.commit.find_git_root", return_value=Path("/tmp/test"))
    @patch("axm_git.tools.commit.stage_spec_files", return_value=None)
    @patch("axm_git.tools.commit.run_git")
    def test_strict_mode_blocks_non_conventional(
        self, mock_git: MagicMock, _mock_stage: MagicMock, _mock_root: MagicMock
    ) -> None:
        """AC4: explicit strict mode turns the warning into a hard failure."""
        mock_git.side_effect = self._side_effect
        result = GitCommitTool().execute(
            path="/tmp/test",
            commits=[{"files": ["a.py"], "message": "wip stuff"}],
            strict=True,
        )
        assert result.success is False
        assert "wip stuff" in (result.error or "")


class TestRunnerAgnosticWording:
    """AC1/AC3: hook-runner-agnostic messaging and stable result key."""

    @patch("axm_git.tools.commit.find_git_root", return_value=Path("/tmp/test"))
    @patch("axm_git.tools.commit.stage_spec_files", return_value=None)
    @patch("axm_git.tools.commit.run_git")
    def test_commit_failure_message_runner_agnostic(
        self, mock_git: MagicMock, _mock_stage: MagicMock, _mock_root: MagicMock
    ) -> None:
        """AC1: a failing commit reports runner-agnostic wording.

        The error must speak of a generic 'hook' check failing, never name
        the ``pre-commit`` tool specifically (git runs whatever the repo's
        ``.git/hooks/pre-commit`` file is — pre-commit OR prek).
        """

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "commit":
                return _fail(stderr="hook error")
            if args[0] == "log":
                return _ok("abc1234")
            return _ok()

        mock_git.side_effect = _side_effect
        result = GitCommitTool().execute(
            path="/tmp/test",
            commits=[{"files": ["a.py"], "message": "fix: a"}],
        )
        assert not result.success
        error = result.error or ""
        assert "hook" in error.lower()
        assert "pre-commit failed" not in error

    @patch("axm_git.tools.commit.find_git_root", return_value=Path("/tmp/test"))
    @patch("axm_git.tools.commit.stage_spec_files", return_value=None)
    @patch("axm_git.tools.commit.run_git")
    def test_result_keeps_precommit_passed_key(
        self, mock_git: MagicMock, _mock_stage: MagicMock, _mock_root: MagicMock
    ) -> None:
        """AC3: the ``precommit_passed`` result key is unchanged (no rename)."""

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "log":
                return _ok("abc1234")
            return _ok()

        mock_git.side_effect = _side_effect
        result = GitCommitTool().execute(
            path="/tmp/test",
            commits=[{"files": ["a.py"], "message": "fix: a"}],
        )
        assert result.success
        assert "precommit_passed" in result.data["results"][0]


class TestEmptyCommitList:
    """commits=[] returns success=False with clear error."""

    def test_empty_list(self) -> None:
        tool = GitCommitTool()
        result = tool.execute(path="/tmp/repo", commits=[])

        assert result.success is False
        assert result.error == "No commits provided"

    def test_none_defaults_to_empty(self) -> None:
        tool = GitCommitTool()
        result = tool.execute(path="/tmp/repo", commits=None)

        assert result.success is False
        assert result.error == "No commits provided"
