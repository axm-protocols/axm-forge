"""Unit tests for structure rules — pure ID/format checks, no I/O."""

from __future__ import annotations

from axm_audit.core.rules.structure import PyprojectCompletenessRule, check_fields


class TestFileExistsRuleUnit:
    """Unit tests for FileExistsRule (no I/O)."""

    def test_rule_id_includes_filename(self) -> None:
        """Rule ID should include the filename."""
        from axm_audit.core.rules.structure import FileExistsRule

        rule = FileExistsRule(file_name="README.md")
        assert rule.rule_id == "FILE_EXISTS_README.md"


class TestDirectoryExistsRuleUnit:
    """Unit tests for DirectoryExistsRule (no I/O)."""

    def test_rule_id_includes_dirname(self) -> None:
        """Rule ID should include the dir name."""
        from axm_audit.core.rules.structure import DirectoryExistsRule

        rule = DirectoryExistsRule(dir_name="tests")
        assert rule.rule_id == "DIR_EXISTS_tests"


# ---------------------------------------------------------------------------
# Merged from tests/unit/core/rules/test_pyproject_helpers.py
# ---------------------------------------------------------------------------


class TestPyprojectCompletenessRuleMeta:
    """Pure-introspection tests on PyprojectCompletenessRule (no I/O)."""

    def test_rule_id(self) -> None:
        """Rule ID should be STRUCTURE_PYPROJECT."""

        assert PyprojectCompletenessRule().rule_id == "STRUCTURE_PYPROJECT"


class TestCheckFields:
    """Tests for the check_fields helper."""

    def test_check_fields_returns_tuple(self) -> None:
        """check_fields({"name": "x"}) returns (1, [8 missing])."""
        present, missing = check_fields({"name": "x"})
        assert present == 1
        assert "description" in missing
        assert "requires-python" in missing
        assert "license" in missing
        assert "authors" in missing
        assert "version" in missing
        assert "urls" in missing
        assert "classifiers" in missing
        assert "readme" in missing

    def test_check_fields_dynamic_version(self) -> None:
        """dynamic=["version"] → version not in missing."""
        _present, missing = check_fields({"name": "x", "dynamic": ["version"]})
        assert "version" not in missing


class TestEdgeCases:
    """Edge-case scenarios for check_fields."""

    def test_empty_project_table(self) -> None:
        """Empty project table → 0 present, 9 missing."""
        present, missing = check_fields({})
        assert present == 0
        assert len(missing) == 9

    def test_dynamic_version_only(self) -> None:
        """dynamic=["version"] but no static version → version present."""
        present, missing = check_fields({"dynamic": ["version"]})
        assert "version" not in missing
        assert present == 1

    def test_urls_present_but_empty(self) -> None:
        """Empty urls dict is falsy → urls counted as missing."""
        _present, missing = check_fields({"name": "x", "urls": {}})
        assert "urls" in missing
