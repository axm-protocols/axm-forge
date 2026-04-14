from __future__ import annotations

from pathlib import Path

from axm_audit.core.rules.structure import DirectoryExistsRule, FileExistsRule

# --- DirectoryExistsRule fix_hint ---


def test_directory_missing_has_fix_hint(tmp_path: Path) -> None:
    rule = DirectoryExistsRule(dir_name="src")
    result = rule.check(tmp_path)
    assert not result.passed
    assert result.fix_hint == "mkdir src"


def test_directory_exists_no_fix_hint(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    rule = DirectoryExistsRule(dir_name="src")
    result = rule.check(tmp_path)
    assert result.passed
    assert result.fix_hint is None


# --- FileExistsRule fix_hint ---


def test_file_missing_has_fix_hint(tmp_path: Path) -> None:
    rule = FileExistsRule(file_name="README.md")
    result = rule.check(tmp_path)
    assert not result.passed
    assert result.fix_hint == "touch README.md"


def test_file_exists_no_fix_hint(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("")
    rule = FileExistsRule(file_name="README.md")
    result = rule.check(tmp_path)
    assert result.passed
    assert result.fix_hint is None


# --- Edge cases ---


def test_nested_dir_name_fix_hint(tmp_path: Path) -> None:
    rule = DirectoryExistsRule(dir_name="src/pkg")
    result = rule.check(tmp_path)
    assert not result.passed
    assert result.fix_hint == "mkdir src/pkg"


def test_dotfile_fix_hint(tmp_path: Path) -> None:
    rule = FileExistsRule(file_name=".gitignore")
    result = rule.check(tmp_path)
    assert not result.passed
    assert result.fix_hint == "touch .gitignore"
