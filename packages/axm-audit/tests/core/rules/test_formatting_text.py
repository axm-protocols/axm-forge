from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from axm_audit.core.rules.quality import FormattingRule

MODULE = "axm_audit.core.rules.quality"


@pytest.fixture()
def rule() -> FormattingRule:
    return FormattingRule()


@pytest.fixture()
def _bypass_early(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub check_src, _get_audit_targets, and run_in_project."""
    monkeypatch.setattr(f"{MODULE}.FormattingRule.check_src", lambda self, p: None)
    monkeypatch.setattr(
        f"{MODULE}._get_audit_targets",
        lambda p: (["src/"], "src/"),
    )
    monkeypatch.setattr(
        f"{MODULE}.run_in_project",
        lambda *a, **kw: MagicMock(stdout="", returncode=0),
    )


def _patch_unformatted(monkeypatch: pytest.MonkeyPatch, files: list[str]) -> None:
    monkeypatch.setattr(
        f"{MODULE}.FormattingRule._parse_unformatted_files",
        lambda self, result: files,
    )


# --- Unit tests ---


@pytest.mark.usefixtures("_bypass_early")
def test_formatting_text_bare_paths(
    rule: FormattingRule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """text= must contain bare file paths, no bullets, no padding."""
    _patch_unformatted(monkeypatch, ["src/a.py", "src/b.py", "src/c.py"])
    result = rule.check(Path("/fake"))
    assert result.text == "src/a.py\nsrc/b.py\nsrc/c.py"


@pytest.mark.usefixtures("_bypass_early")
def test_formatting_text_none_on_pass(
    rule: FormattingRule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """text= must be None when no unformatted files."""
    _patch_unformatted(monkeypatch, [])
    result = rule.check(Path("/fake"))
    assert result.text is None


# --- Edge cases ---


@pytest.mark.usefixtures("_bypass_early")
def test_formatting_text_cap_at_20(
    rule: FormattingRule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """text= must contain at most 20 lines, no trailing newline."""
    files = [f"src/file_{i}.py" for i in range(30)]
    _patch_unformatted(monkeypatch, files)
    result = rule.check(Path("/fake"))
    assert result.text is not None
    lines = result.text.split("\n")
    assert len(lines) == 20
    assert not result.text.endswith("\n")


@pytest.mark.usefixtures("_bypass_early")
def test_formatting_text_single_file(
    rule: FormattingRule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Single unformatted file — no trailing newline."""
    _patch_unformatted(monkeypatch, ["src/only.py"])
    result = rule.check(Path("/fake"))
    assert result.text == "src/only.py"
