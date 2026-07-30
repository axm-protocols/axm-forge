"""Tests for checks/_utils.py — shared TOML loading utility."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from axm_init.checks._utils import (
    load_toml_with_workspace_fallback,
)

# ---------------------------------------------------------------------------
# Functional: load_toml_with_workspace_fallback
# ---------------------------------------------------------------------------


class TestNoWorkspaceNoMerge:
    """Standalone project (no workspace root) returns member data as-is."""

    def test_no_workspace_no_merge(self, tmp_path: Path) -> None:
        member_data = {"tool": {"mypy": {"strict": True}}, "project": {"name": "solo"}}

        with (
            patch("axm_init.checks._utils.load_toml", return_value=member_data),
            patch("axm_init.checks._workspace.find_workspace_root", return_value=None),
        ):
            result = load_toml_with_workspace_fallback(tmp_path)

        assert result == member_data


class TestWorkspaceFallbackIntegration:
    """Integration test: workspace root + member configs are deep-merged."""

    def test_workspace_merges_root_and_member(self, tmp_path: Path) -> None:
        root_path = tmp_path / "root"
        member_path = tmp_path / "member"
        root_path.mkdir()
        member_path.mkdir()

        root_data = {
            "tool": {
                "mypy": {"strict": True},
                "coverage": {
                    "run": {"relative_files": True},
                    "xml": {"output": "coverage.xml"},
                },
            },
        }
        member_data = {
            "tool": {
                "mypy": {"pretty": True},
                "coverage": {
                    "run": {"branch": True, "source": ["src"]},
                    "report": {"omit": ["tests/*"]},
                },
            },
            "project": {"name": "member-pkg"},
        }

        def fake_load_toml(path: Path) -> dict[str, Any]:
            if path == member_path:
                return member_data
            if path == root_path:
                return root_data
            return {}

        with (
            patch("axm_init.checks._utils.load_toml", side_effect=fake_load_toml),
            patch(
                "axm_init.checks._workspace.find_workspace_root", return_value=root_path
            ),
        ):
            result = load_toml_with_workspace_fallback(member_path)

        assert result is not None
        tool = result["tool"]
        # AC3: mypy — root strict + member pretty both visible
        assert tool["mypy"]["strict"] is True
        assert tool["mypy"]["pretty"] is True
        # AC4: coverage — root relative_files + member source/branch/omit
        assert tool["coverage"]["run"]["relative_files"] is True
        assert tool["coverage"]["run"]["branch"] is True
        assert tool["coverage"]["run"]["source"] == ["src"]
        # Root-only xml preserved (AC7)
        assert tool["coverage"]["xml"] == {"output": "coverage.xml"}
        # Member-only report preserved (AC6)
        assert tool["coverage"]["report"] == {"omit": ["tests/*"]}
        # Non-tool keys from member preserved
        assert result["project"] == {"name": "member-pkg"}
