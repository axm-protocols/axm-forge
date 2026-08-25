"""Split from ``test_pyramid_directory_layout.py``."""

from pathlib import Path

import pytest

from axm_audit.core.rules.structure import DirectoryExistsRule


class TestDirectoryExistsRuleIO:
    """Integration tests for DirectoryExistsRule (real filesystem)."""

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


def test_directory_exists_no_fix_hint(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    rule = DirectoryExistsRule(dir_name="src")
    result = rule.check(tmp_path)
    assert result.passed
    assert result.fix_hint is None
