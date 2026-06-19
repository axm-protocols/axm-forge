"""Unit tests for the Node subprocess runner helpers."""

from __future__ import annotations

from pathlib import Path

from axm_audit.core.rules.node._runner import _resolve_cmd, node_tool_available


class TestNodeToolAvailable:
    """``node_tool_available`` requires a real local binary (no false green)."""

    def test_missing_local_binary_is_unavailable(self, tmp_path: Path) -> None:
        """No node_modules/.bin/eslint → unavailable, even if npx is on PATH.

        This is the guard against the false-green env failure: ``npx
        --no-install`` of an uninstalled tool exits non-zero with empty output,
        which a scorer would otherwise read as "ran clean".
        """
        assert node_tool_available(tmp_path, "eslint") is False

    def test_installed_local_binary_is_available(self, tmp_path: Path) -> None:
        """A file at node_modules/.bin/<binary> counts as available."""
        bin_dir = tmp_path / "node_modules" / ".bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "eslint").write_text("#!/bin/sh\n")
        assert node_tool_available(tmp_path, "eslint") is True


class TestResolveCmd:
    """``_resolve_cmd`` prefers the project-local binary."""

    def test_uses_local_binary_when_present(self, tmp_path: Path) -> None:
        """When the local binary exists, the argv points at it directly."""
        bin_dir = tmp_path / "node_modules" / ".bin"
        bin_dir.mkdir(parents=True)
        local = bin_dir / "eslint"
        local.write_text("#!/bin/sh\n")
        cmd = _resolve_cmd(tmp_path, "eslint", ["--format", "json"])
        assert cmd == [str(local), "--format", "json"]
