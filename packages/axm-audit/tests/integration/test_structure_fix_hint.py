from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.structure import DirectoryExistsRule, FileExistsRule

# --- Missing target → fix_hint populated ---


@pytest.mark.parametrize(
    ("rule", "expected_hint"),
    [
        pytest.param(
            DirectoryExistsRule(dir_name="src"),
            "mkdir src",
            id="directory_missing",
        ),
        pytest.param(
            FileExistsRule(file_name="README.md"),
            "touch README.md",
            id="file_missing",
        ),
        pytest.param(
            DirectoryExistsRule(dir_name="src/pkg"),
            "mkdir src/pkg",
            id="nested_dir_name",
        ),
        pytest.param(
            FileExistsRule(file_name=".gitignore"),
            "touch .gitignore",
            id="dotfile",
        ),
    ],
)
def test_missing_target_has_fix_hint(
    tmp_path: Path,
    rule: DirectoryExistsRule | FileExistsRule,
    expected_hint: str,
) -> None:
    result = rule.check(tmp_path)
    assert not result.passed
    assert result.fix_hint == expected_hint


# --- Existing target → no fix_hint ---


def test_directory_exists_no_fix_hint(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    rule = DirectoryExistsRule(dir_name="src")
    result = rule.check(tmp_path)
    assert result.passed
    assert result.fix_hint is None


def test_file_exists_no_fix_hint(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("")
    rule = FileExistsRule(file_name="README.md")
    result = rule.check(tmp_path)
    assert result.passed
    assert result.fix_hint is None
