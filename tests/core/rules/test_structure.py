"""Tests for structure rules — FileExistsRule, DirectoryExistsRule."""

from __future__ import annotations

from pathlib import Path


class TestFileExistsRule:
    """Tests for FileExistsRule."""

    def test_file_exists(self, tmp_path: Path) -> None:
        """Existing file passes."""
        from axm_audit.core.rules.structure import FileExistsRule

        (tmp_path / "README.md").write_text("# Hello")

        rule = FileExistsRule(file_name="README.md")
        result = rule.check(tmp_path)

        assert result.passed is True
        assert "exists" in result.message

    def test_file_missing(self, tmp_path: Path) -> None:
        """Missing file fails."""
        from axm_audit.core.rules.structure import FileExistsRule

        rule = FileExistsRule(file_name="README.md")
        result = rule.check(tmp_path)

        assert result.passed is False
        assert "not found" in result.message

    def test_rule_id_includes_filename(self) -> None:
        """Rule ID should include the filename."""
        from axm_audit.core.rules.structure import FileExistsRule

        rule = FileExistsRule(file_name="README.md")
        assert rule.rule_id == "FILE_EXISTS_README.md"


class TestDirectoryExistsRule:
    """Tests for DirectoryExistsRule."""

    def test_directory_exists(self, tmp_path: Path) -> None:
        """Existing directory passes."""
        from axm_audit.core.rules.structure import DirectoryExistsRule

        (tmp_path / "src").mkdir()

        rule = DirectoryExistsRule(dir_name="src")
        result = rule.check(tmp_path)

        assert result.passed is True
        assert "exists" in result.message

    def test_directory_missing(self, tmp_path: Path) -> None:
        """Missing directory fails."""
        from axm_audit.core.rules.structure import DirectoryExistsRule

        rule = DirectoryExistsRule(dir_name="src")
        result = rule.check(tmp_path)

        assert result.passed is False
        assert "not found" in result.message

    def test_rule_id_includes_dirname(self) -> None:
        """Rule ID should include the dir name."""
        from axm_audit.core.rules.structure import DirectoryExistsRule

        rule = DirectoryExistsRule(dir_name="tests")
        assert rule.rule_id == "DIR_EXISTS_tests"
