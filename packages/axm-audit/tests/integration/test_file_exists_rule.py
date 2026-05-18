"""Split from ``test_pyramid_directory_layout.py``."""

from pathlib import Path

import pytest

from axm_audit.core.rules.structure import FileExistsRule


class TestFileExistsRuleIO:
    """Integration tests for FileExistsRule (real filesystem)."""

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


def test_file_exists_no_fix_hint(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("")
    rule = FileExistsRule(file_name="README.md")
    result = rule.check(tmp_path)
    assert result.passed
    assert result.fix_hint is None
