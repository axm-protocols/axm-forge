"""Tests for structure rules — FileExistsRule, DirectoryExistsRule."""

from __future__ import annotations

from pathlib import Path

import pytest


class TestFileExistsRule:
    """Tests for FileExistsRule."""

    @pytest.mark.parametrize(
        ("create", "expected_passed", "expected_substr"),
        [
            pytest.param(True, True, "exists", id="exists"),
            pytest.param(False, False, "not found", id="missing"),
        ],
    )
    def test_file_presence(
        self,
        tmp_path: Path,
        create: bool,
        expected_passed: bool,
        expected_substr: str,
    ) -> None:
        """Existing file passes; missing file fails."""
        from axm_audit.core.rules.structure import FileExistsRule

        if create:
            (tmp_path / "README.md").write_text("# Hello")

        rule = FileExistsRule(file_name="README.md")
        result = rule.check(tmp_path)

        assert result.passed is expected_passed
        assert expected_substr in result.message

    def test_rule_id_includes_filename(self) -> None:
        """Rule ID should include the filename."""
        from axm_audit.core.rules.structure import FileExistsRule

        rule = FileExistsRule(file_name="README.md")
        assert rule.rule_id == "FILE_EXISTS_README.md"


class TestDirectoryExistsRule:
    """Tests for DirectoryExistsRule."""

    @pytest.mark.parametrize(
        ("create", "expected_passed", "expected_substr"),
        [
            pytest.param(True, True, "exists", id="exists"),
            pytest.param(False, False, "not found", id="missing"),
        ],
    )
    def test_directory_presence(
        self,
        tmp_path: Path,
        create: bool,
        expected_passed: bool,
        expected_substr: str,
    ) -> None:
        """Existing directory passes; missing directory fails."""
        from axm_audit.core.rules.structure import DirectoryExistsRule

        if create:
            (tmp_path / "src").mkdir()

        rule = DirectoryExistsRule(dir_name="src")
        result = rule.check(tmp_path)

        assert result.passed is expected_passed
        assert expected_substr in result.message

    def test_rule_id_includes_dirname(self) -> None:
        """Rule ID should include the dir name."""
        from axm_audit.core.rules.structure import DirectoryExistsRule

        rule = DirectoryExistsRule(dir_name="tests")
        assert rule.rule_id == "DIR_EXISTS_tests"
