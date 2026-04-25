"""Public-API tests for ``SecurityRule`` text formatting.

These tests drive ``SecurityRule().check()`` (the public boundary) and
monkeypatch the module-level ``_run_bandit`` function to inject canned
results, replacing the old direct ``_build_security_result`` import.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.models.results import CheckResult


def _make_result(
    severity: str, test_id: str, text: str, filename: str, line: int
) -> dict[str, str | int]:
    """Build a fake Bandit result dict."""
    return {
        "issue_severity": severity,
        "test_id": test_id,
        "issue_text": text,
        "filename": filename,
        "line_number": line,
    }


def _make_project(tmp_path: Path) -> Path:
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\nversion = "0.1"\n'
    )
    return tmp_path


def _check_with_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bandit_results: list[dict[str, str | int]],
) -> CheckResult:
    from axm_audit.core.rules import security as sec_mod
    from axm_audit.core.rules.security import SecurityRule

    monkeypatch.setattr(
        sec_mod,
        "_run_bandit",
        lambda src_path, project_path: {"results": bandit_results},
    )
    return SecurityRule().check(_make_project(tmp_path))


# --- Unit tests ---


def test_text_format_compact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """2 HIGH + 1 MED issues produce compact bullet lines."""
    results = [
        _make_result("HIGH", "B105", "Hardcoded password", "/src/auth.py", 10),
        _make_result("HIGH", "B106", "Hardcoded secret", "/src/config.py", 42),
        _make_result("MEDIUM", "B301", "Pickle usage", "/src/utils.py", 55),
    ]
    result = _check_with_results(tmp_path, monkeypatch, results)
    assert result.text is not None
    lines = result.text.splitlines()
    assert len(lines) == 3
    assert lines[0] == "\u2022 H B105 auth.py:10 Hardcoded password"
    assert lines[1] == "\u2022 H B106 config.py:42 Hardcoded secret"
    assert lines[2] == "\u2022 M B301 utils.py:55 Pickle usage"


def test_text_none_when_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No issues means text=None."""
    result = _check_with_results(tmp_path, monkeypatch, [])
    assert result.text is None


def test_text_none_when_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty results: text=None and rule passes."""
    result = _check_with_results(tmp_path, monkeypatch, [])
    assert result.text is None
    assert result.passed is True


# --- Edge cases ---


def test_single_issue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Single HIGH issue produces a single bullet line."""
    results = [
        _make_result("HIGH", "B105", "Hardcoded password", "/src/auth.py", 42),
    ]
    result = _check_with_results(tmp_path, monkeypatch, results)
    assert result.text == "\u2022 H B105 auth.py:42 Hardcoded password"


def test_five_issues_high_sorted_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """5 mixed-severity issues: HIGH sorted before MEDIUM."""
    results = [
        _make_result("MEDIUM", "B301", "Pickle usage", "/src/a.py", 1),
        _make_result("HIGH", "B105", "Hardcoded password", "/src/b.py", 2),
        _make_result("MEDIUM", "B302", "Marshal usage", "/src/c.py", 3),
        _make_result("HIGH", "B106", "Hardcoded secret", "/src/d.py", 4),
        _make_result("MEDIUM", "B303", "MD5 usage", "/src/e.py", 5),
    ]
    result = _check_with_results(tmp_path, monkeypatch, results)
    assert result.text is not None
    lines = result.text.splitlines()
    assert len(lines) == 5
    assert lines[0].startswith("\u2022 H")
    assert lines[1].startswith("\u2022 H")
    assert lines[2].startswith("\u2022 M")
    assert lines[3].startswith("\u2022 M")
    assert lines[4].startswith("\u2022 M")
