"""Tests for checks/_utils.py — shared TOML loading utility."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from axm_init.checks._utils import (
    _load_toml_with_workspace_fallback,
    _merge_tool_sections,
)


class TestLoadToml:
    """Tests for _load_toml()."""

    def test_load_toml_valid(self, tmp_path: Path) -> None:
        """Valid pyproject.toml is parsed correctly."""
        from axm_init.checks._utils import _load_toml

        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test-pkg"\n')
        data = _load_toml(tmp_path)
        assert data is not None
        assert data["project"]["name"] == "test-pkg"

    def test_load_toml_missing(self, tmp_path: Path) -> None:
        """Missing pyproject.toml returns None."""
        from axm_init.checks._utils import _load_toml

        data = _load_toml(tmp_path)
        assert data is None

    def test_load_toml_corrupt(self, tmp_path: Path) -> None:
        """Corrupt TOML returns None."""
        from axm_init.checks._utils import _load_toml

        (tmp_path / "pyproject.toml").write_text("{{invalid toml}}")
        data = _load_toml(tmp_path)
        assert data is None


# ---------------------------------------------------------------------------
# Unit tests: _merge_tool_sections
# ---------------------------------------------------------------------------


class TestDeepMergeNestedDicts:
    """base has coverage.run.relative_files, override adds coverage.run.branch."""

    def test_deep_merge_nested_dicts(self) -> None:
        base = {"tool": {"coverage": {"run": {"relative_files": True}}}}
        override = {"tool": {"coverage": {"run": {"branch": True}}}}

        result = _merge_tool_sections(base, override)

        assert result["tool"]["coverage"]["run"]["relative_files"] is True
        assert result["tool"]["coverage"]["run"]["branch"] is True


class TestDeepMergeMemberWinsConflict:
    """When both base and override define the same leaf, override wins."""

    def test_deep_merge_member_wins_conflict(self) -> None:
        base = {"tool": {"mypy": {"strict": True}}}
        override = {"tool": {"mypy": {"strict": False}}}

        result = _merge_tool_sections(base, override)

        assert result["tool"]["mypy"]["strict"] is False


class TestDeepMergeListsNotMerged:
    """Lists are NOT merged — member list replaces root list entirely."""

    def test_deep_merge_lists_not_merged(self) -> None:
        base = {"tool": {"ruff": {"lint": {"select": ["E", "F"]}}}}
        override = {"tool": {"ruff": {"lint": {"select": ["I"]}}}}

        result = _merge_tool_sections(base, override)

        assert result["tool"]["ruff"]["lint"]["select"] == ["I"]


class TestDeepMergeRootOnlyKey:
    """Root-only key (not in member) is preserved."""

    def test_deep_merge_root_only_key(self) -> None:
        base = {
            "tool": {
                "coverage": {
                    "run": {"relative_files": True},
                    "xml": {"output": "cov.xml"},
                }
            }
        }
        override = {"tool": {"coverage": {"run": {"branch": True}}}}

        result = _merge_tool_sections(base, override)

        assert result["tool"]["coverage"]["xml"] == {"output": "cov.xml"}


class TestDeepMergeMemberOnlyKey:
    """Member-only key (not in root) is preserved."""

    def test_deep_merge_member_only_key(self) -> None:
        base = {"tool": {"mypy": {"strict": True}}}
        override = {"tool": {"deptry": {"enabled": True}}}

        result = _merge_tool_sections(base, override)

        assert result["tool"]["deptry"] == {"enabled": True}
        assert result["tool"]["mypy"] == {"strict": True}


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestMemberEmptyToolSection:
    """Member has an empty tool section — root config used entirely."""

    def test_member_empty_tool_section(self) -> None:
        base = {"tool": {"mypy": {"strict": True, "pretty": True}}}
        override: dict[str, Any] = {"tool": {"mypy": {}}}

        result = _merge_tool_sections(base, override)

        assert result["tool"]["mypy"] == {"strict": True, "pretty": True}


class TestDeeplyNestedOverride:
    """Deeply nested keys from root and member are both preserved."""

    def test_deeply_nested_override(self) -> None:
        base = {"tool": {"ruff": {"lint": {"isort": {"known-first-party": ["axm"]}}}}}
        override = {"tool": {"ruff": {"lint": {"select": ["I"]}}}}

        result = _merge_tool_sections(base, override)

        assert result["tool"]["ruff"]["lint"]["isort"] == {"known-first-party": ["axm"]}
        assert result["tool"]["ruff"]["lint"]["select"] == ["I"]


class TestNonDictToolValue:
    """Non-dict tool value — member replaces root (no recursion)."""

    def test_non_dict_tool_value_string(self) -> None:
        base = {"tool": {"setuptools": "legacy"}}
        override = {"tool": {"setuptools": "modern"}}

        result = _merge_tool_sections(base, override)

        assert result["tool"]["setuptools"] == "modern"

    def test_non_dict_tool_value_list(self) -> None:
        base = {"tool": {"setuptools": ["a", "b"]}}
        override = {"tool": {"setuptools": ["c"]}}

        result = _merge_tool_sections(base, override)

        assert result["tool"]["setuptools"] == ["c"]


# ---------------------------------------------------------------------------
# Functional: _load_toml_with_workspace_fallback
# ---------------------------------------------------------------------------


class TestNoWorkspaceNoMerge:
    """Standalone project (no workspace root) returns member data as-is."""

    def test_no_workspace_no_merge(self, tmp_path: Path) -> None:
        member_data = {"tool": {"mypy": {"strict": True}}, "project": {"name": "solo"}}

        with (
            patch("axm_init.checks._utils._load_toml", return_value=member_data),
            patch("axm_init.checks._workspace.find_workspace_root", return_value=None),
        ):
            result = _load_toml_with_workspace_fallback(tmp_path)

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
            patch("axm_init.checks._utils._load_toml", side_effect=fake_load_toml),
            patch(
                "axm_init.checks._workspace.find_workspace_root", return_value=root_path
            ),
        ):
            result = _load_toml_with_workspace_fallback(member_path)

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
