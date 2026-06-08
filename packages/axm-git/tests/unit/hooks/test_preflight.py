"""Unit tests for axm_git.hooks.preflight (no real I/O)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from axm_git.hooks.preflight import PreflightHook, truncate_diff


def _ok(stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=[], returncode=0, stdout=stdout, stderr=stderr
    )


class TestCollectStatusFilesViaHook:
    """Drive PreflightHook.execute with monkeypatched ``-z`` status stdout.

    All real I/O is suppressed: ``find_git_root`` is patched to a fake root and
    every ``run_git`` call is fed from a scripted ``side_effect`` (status first,
    then empty diff-stat and diff). Asserts the public ``metadata['files']``
    shape (list of ``{'path', 'status'}`` dicts) survives the new parser.
    """

    @patch("axm_git.hooks.preflight.find_git_root")
    @patch("axm_git.hooks.preflight.run_git")
    def test_status_rename_parsed_to_new_path(
        self, mock_git: MagicMock, mock_root: MagicMock
    ) -> None:
        """AC1: a rename entry resolves to the new (destination) path."""
        mock_root.return_value = Path("/repo")
        # ``-z`` rename record: ``XY <space> dest\0 src\0``.
        mock_git.side_effect = [
            _ok(stdout="R  new.py\x00old.py\x00"),  # status --porcelain -z
            _ok(stdout=""),  # diff --stat
            _ok(stdout=""),  # diff
        ]
        result = PreflightHook().execute({}, path="/repo")

        assert result.success
        files = result.metadata["files"]
        assert len(files) == 1
        assert files[0]["path"] == "new.py"
        assert files[0]["status"] == "R"

    @patch("axm_git.hooks.preflight.find_git_root")
    @patch("axm_git.hooks.preflight.run_git")
    def test_status_spaced_path_unquoted(
        self, mock_git: MagicMock, mock_root: MagicMock
    ) -> None:
        """AC2: a path containing spaces is returned unquoted and unescaped."""
        mock_root.return_value = Path("/repo")
        mock_git.side_effect = [
            _ok(stdout=" M my file.py\x00"),  # status --porcelain -z
            _ok(stdout=""),
            _ok(stdout=""),
        ]
        result = PreflightHook().execute({}, path="/repo")

        assert result.success
        files = result.metadata["files"]
        assert len(files) == 1
        assert files[0]["path"] == "my file.py"

    @patch("axm_git.hooks.preflight.find_git_root")
    @patch("axm_git.hooks.preflight.run_git")
    def test_status_ordinary_entries_still_parse(
        self, mock_git: MagicMock, mock_root: MagicMock
    ) -> None:
        """AC4: ordinary modified/added/untracked entries still parse."""
        mock_root.return_value = Path("/repo")
        mock_git.side_effect = [
            _ok(stdout=" M README.md\x00A  added.py\x00?? new.py\x00"),
            _ok(stdout=""),
            _ok(stdout=""),
        ]
        result = PreflightHook().execute({}, path="/repo")

        assert result.success
        files = result.metadata["files"]
        by_path = {f["path"]: f["status"] for f in files}
        assert by_path == {"README.md": "M", "added.py": "A", "new.py": "??"}


class TestTruncateDiff:
    """Unit-scope tests for axm_git.hooks.preflight.truncate_diff (no I/O)."""

    def test_truncate_diff_under_limit(self) -> None:
        """10 lines with max=200 returns all lines stripped."""
        stdout = "\n".join(f"line {i}" for i in range(10))
        result = truncate_diff(stdout, max_lines=200)
        assert result == stdout.strip()

    def test_truncate_diff_over_limit(self) -> None:
        """300 lines with max=200 returns first 200 lines."""
        lines = [f"line {i}" for i in range(300)]
        stdout = "\n".join(lines)
        result = truncate_diff(stdout, max_lines=200)
        expected = "\n".join(lines[:200])
        assert result == expected

    def test_truncate_diff_zero_lines(self) -> None:
        """max_lines=0 returns empty string (user disables diff)."""
        stdout = "\n".join(f"line {i}" for i in range(10))
        result = truncate_diff(stdout, max_lines=0)
        assert result == ""


def test_preflight_hook_discoverable() -> None:
    from importlib.metadata import entry_points

    eps = entry_points(group="axm.hooks")
    names = [ep.name for ep in eps]
    assert "git:preflight" in names


def test_preflight_hook_loads() -> None:
    from importlib.metadata import entry_points

    eps = entry_points(group="axm.hooks")
    ep = next(ep for ep in eps if ep.name == "git:preflight")
    assert ep.load() is PreflightHook
