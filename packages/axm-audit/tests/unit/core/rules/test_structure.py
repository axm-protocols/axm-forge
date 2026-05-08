"""Unit tests for structure rules — pure ID/format checks, no I/O."""

from __future__ import annotations


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
