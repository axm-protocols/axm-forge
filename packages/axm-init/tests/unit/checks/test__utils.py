"""Unit tests for checks/_utils.py — merge_tool_sections (pure logic)."""

from __future__ import annotations

from typing import Any

import pytest

from axm_init.checks._utils import merge_tool_sections


class TestDeepMergeNestedDicts:
    """base has coverage.run.relative_files, override adds coverage.run.branch."""

    def test_deep_merge_nested_dicts(self) -> None:
        base = {"tool": {"coverage": {"run": {"relative_files": True}}}}
        override = {"tool": {"coverage": {"run": {"branch": True}}}}

        result = merge_tool_sections(base, override)

        assert result["tool"]["coverage"]["run"]["relative_files"] is True
        assert result["tool"]["coverage"]["run"]["branch"] is True


class TestDeepMergeMemberWinsConflict:
    """When both base and override define the same leaf, override wins."""

    def test_deep_merge_member_wins_conflict(self) -> None:
        base = {"tool": {"mypy": {"strict": True}}}
        override = {"tool": {"mypy": {"strict": False}}}

        result = merge_tool_sections(base, override)

        assert result["tool"]["mypy"]["strict"] is False


class TestDeepMergeListsNotMerged:
    """Lists are NOT merged — member list replaces root list entirely."""

    def test_deep_merge_lists_not_merged(self) -> None:
        base = {"tool": {"ruff": {"lint": {"select": ["E", "F"]}}}}
        override = {"tool": {"ruff": {"lint": {"select": ["I"]}}}}

        result = merge_tool_sections(base, override)

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

        result = merge_tool_sections(base, override)

        assert result["tool"]["coverage"]["xml"] == {"output": "cov.xml"}


class TestDeepMergeMemberOnlyKey:
    """Member-only key (not in root) is preserved."""

    def test_deep_merge_member_only_key(self) -> None:
        base = {"tool": {"mypy": {"strict": True}}}
        override = {"tool": {"deptry": {"enabled": True}}}

        result = merge_tool_sections(base, override)

        assert result["tool"]["deptry"] == {"enabled": True}
        assert result["tool"]["mypy"] == {"strict": True}


class TestDeeplyNestedOverride:
    """Deeply nested keys from root and member are both preserved."""

    def test_deeply_nested_override(self) -> None:
        base = {"tool": {"ruff": {"lint": {"isort": {"known-first-party": ["axm"]}}}}}
        override = {"tool": {"ruff": {"lint": {"select": ["I"]}}}}

        result = merge_tool_sections(base, override)

        assert result["tool"]["ruff"]["lint"]["isort"] == {"known-first-party": ["axm"]}
        assert result["tool"]["ruff"]["lint"]["select"] == ["I"]


@pytest.mark.parametrize(
    ("base", "override", "key", "expected"),
    [
        pytest.param(
            {"tool": {"mypy": {"strict": True, "pretty": True}}},
            {"tool": {"mypy": {}}},
            "mypy",
            {"strict": True, "pretty": True},
            id="member_empty_tool_section",
        ),
        pytest.param(
            {"tool": {"setuptools": "legacy"}},
            {"tool": {"setuptools": "modern"}},
            "setuptools",
            "modern",
            id="non_dict_tool_value_string",
        ),
        pytest.param(
            {"tool": {"setuptools": ["a", "b"]}},
            {"tool": {"setuptools": ["c"]}},
            "setuptools",
            ["c"],
            id="non_dict_tool_value_list",
        ),
    ],
)
def test_merge_tool_sections_non_recursive_override(
    base: dict[str, Any],
    override: dict[str, Any],
    key: str,
    expected: object,
) -> None:
    """Non-recursive override branches: empty member dict & non-dict leaf values."""
    result = merge_tool_sections(base, override)

    assert result["tool"][key] == expected
