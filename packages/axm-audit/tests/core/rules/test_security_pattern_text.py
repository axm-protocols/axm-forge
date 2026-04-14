from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.practices import SecurityPatternRule


@pytest.fixture
def rule() -> SecurityPatternRule:
    return SecurityPatternRule()


def _make_src_file(tmp_path: Path, filename: str, content: str) -> None:
    src = tmp_path / "src"
    src.mkdir(exist_ok=True)
    (src / filename).write_text(content)


def test_fail_text_contains_matches(tmp_path: Path, rule: SecurityPatternRule) -> None:
    """result.text contains one bullet per match when secrets are found."""
    _make_src_file(tmp_path, "bad.py", 'password = "secret"\napi_key = "key"\n')
    result = rule.check(tmp_path)

    assert result.text is not None
    assert "\u2022 bad.py:" in result.text
    lines = result.text.strip().split("\n")
    assert len(lines) == 2


def test_pass_text_is_none(tmp_path: Path, rule: SecurityPatternRule) -> None:
    """result.text is None when no secrets are found."""
    _make_src_file(tmp_path, "clean.py", "x = 1\ny = 2\n")
    result = rule.check(tmp_path)

    assert result.text is None


def test_text_bullet_format(tmp_path: Path, rule: SecurityPatternRule) -> None:
    """Bullet format: 5-space indent + bullet + file:line + pattern."""
    _make_src_file(tmp_path, "bad.py", '\npassword = "secret"\n')
    result = rule.check(tmp_path)

    assert result.text is not None
    assert result.text == "     \u2022 bad.py:2 password"


def test_early_result_no_text(tmp_path: Path, rule: SecurityPatternRule) -> None:
    """No src/ directory -> early result has no text."""
    result = rule.check(tmp_path)

    assert result.text is None


def test_multiple_patterns_same_file(tmp_path: Path, rule: SecurityPatternRule) -> None:
    """Multiple matches produce one bullet each with correct line numbers."""
    _make_src_file(tmp_path, "bad.py", 'password = "x"\ntoken = "y"\n')
    result = rule.check(tmp_path)

    assert result.text is not None
    lines = result.text.strip().split("\n")
    assert len(lines) == 2
    assert "bad.py:1" in lines[0]
    assert "bad.py:2" in lines[1]
