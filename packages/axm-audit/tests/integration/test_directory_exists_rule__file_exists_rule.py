"""Split from ``test_structure_fix_hint.py``."""

from pathlib import Path

import pytest

from axm_audit.core.rules.structure import DirectoryExistsRule, FileExistsRule


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
