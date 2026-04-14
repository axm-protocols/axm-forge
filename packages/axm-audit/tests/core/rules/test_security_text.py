from __future__ import annotations

from axm_audit.core.rules.security import _build_security_result


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


# --- Unit tests ---


def test_text_format_compact() -> None:
    """2 HIGH + 1 MED issues produce compact bullet lines."""
    results = [
        _make_result("HIGH", "B105", "Hardcoded password", "/src/auth.py", 10),
        _make_result("HIGH", "B106", "Hardcoded secret", "/src/config.py", 42),
        _make_result("MEDIUM", "B301", "Pickle usage", "/src/utils.py", 55),
    ]
    result = _build_security_result("SEC001", results)
    assert result.text is not None
    lines = result.text.splitlines()
    assert len(lines) == 3
    assert lines[0] == "• H B105 auth.py:10 Hardcoded password"
    assert lines[1] == "• H B106 config.py:42 Hardcoded secret"
    assert lines[2] == "• M B301 utils.py:55 Pickle usage"


def test_text_none_when_clean() -> None:
    """No issues means text=None."""
    result = _build_security_result("SEC001", [])
    assert result.text is None


def test_text_none_when_error() -> None:
    """Bandit FileNotFoundError yields empty results, so text=None."""
    result = _build_security_result("SEC001", [])
    assert result.text is None
    assert result.passed is True


# --- Edge cases ---


def test_single_issue() -> None:
    """Single HIGH issue produces a single bullet line."""
    results = [
        _make_result("HIGH", "B105", "Hardcoded password", "/src/auth.py", 42),
    ]
    result = _build_security_result("SEC001", results)
    assert result.text == "• H B105 auth.py:42 Hardcoded password"


def test_five_issues_high_sorted_first() -> None:
    """5 mixed-severity issues: HIGH sorted before MEDIUM."""
    results = [
        _make_result("MEDIUM", "B301", "Pickle usage", "/src/a.py", 1),
        _make_result("HIGH", "B105", "Hardcoded password", "/src/b.py", 2),
        _make_result("MEDIUM", "B302", "Marshal usage", "/src/c.py", 3),
        _make_result("HIGH", "B106", "Hardcoded secret", "/src/d.py", 4),
        _make_result("MEDIUM", "B303", "MD5 usage", "/src/e.py", 5),
    ]
    result = _build_security_result("SEC001", results)
    assert result.text is not None
    lines = result.text.splitlines()
    assert len(lines) == 5
    assert lines[0].startswith("• H")
    assert lines[1].startswith("• H")
    assert lines[2].startswith("• M")
    assert lines[3].startswith("• M")
    assert lines[4].startswith("• M")
