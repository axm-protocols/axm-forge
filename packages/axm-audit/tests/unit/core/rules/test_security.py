"""Unit-scope tests for SecurityRule."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from axm_audit.core.rules import security as security_mod
from axm_audit.core.rules.security import SecurityRule, run_bandit

_LOGGER_NAME = "axm_audit.core.rules.security"


class TestUnitScope:
    """Unit-scope tests for SecurityRule."""

    def test_rule_id(self) -> None:
        """Rule ID should be QUALITY_SECURITY."""
        rule = SecurityRule()
        assert rule.rule_id == "QUALITY_SECURITY"


class TestSecurityPatternRuleUnit:
    """Tests for SecurityPatternRule (pure)."""

    def test_rule_id_format(self) -> None:
        """Rule ID should be PRACTICE_SECURITY."""
        from axm_audit.core.rules.security import SecurityPatternRule

        rule = SecurityPatternRule()
        assert rule.rule_id == "PRACTICE_SECURITY"


def test_security_pattern_rule_in_security_bucket() -> None:
    """SecurityPatternRule must be registered in the security bucket."""
    import axm_audit.core.rules  # noqa: F401  (fire decorators)
    from axm_audit.core.rules.base import get_registry

    registry = get_registry()
    bucket = registry["security"]
    names = {cls.__name__ for cls in bucket}
    assert "SecurityPatternRule" in names


def _scan_secret_count(tmp_path: Path, source: str) -> int:
    """Drive the public boundary: write source under src/ and count secret matches."""
    from axm_audit.core.rules.security import SecurityPatternRule

    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "mod.py").write_text(source)
    result = SecurityPatternRule().check(tmp_path)
    assert result.details is not None
    count = result.details["secret_count"]
    assert isinstance(count, int)
    return count


def test_placeholder_password_not_flagged(tmp_path: Path) -> None:
    """AC2: a placeholder password value ('changeme') yields 0 secret matches."""
    assert _scan_secret_count(tmp_path, 'password = "changeme"\n') == 0


def test_angle_bracket_placeholder_not_flagged(tmp_path: Path) -> None:
    """AC2: an angle-bracket placeholder ('<your-key>') yields 0 matches."""
    assert _scan_secret_count(tmp_path, 'api_key = "<your-key>"\n') == 0


def test_real_hex_secret_flagged(tmp_path: Path) -> None:
    """AC4: a real-looking 40-char hex token assigned to secret is flagged."""
    hex_token = "a3f9c1" + "0" * 34
    assert _scan_secret_count(tmp_path, f'secret = "{hex_token}"\n') == 1


# ---------------------------------------------------------------------------
# Merged from test_security_bandit_warn.py
# ---------------------------------------------------------------------------


def _fake_runner(
    returncode: int, stdout: str = "", stderr: str = ""
) -> Callable[..., SimpleNamespace]:
    def _runner(*args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)

    return _runner


def test_bandit_rc1_empty_stdout_warns(monkeypatch, caplog):
    monkeypatch.setattr(
        security_mod,
        "run_in_project",
        _fake_runner(returncode=1, stdout="", stderr="some banner"),
    )
    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        result = run_bandit(Path("/tmp/src"), Path("/tmp"))

    assert result == {}
    warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and r.name == _LOGGER_NAME
    ]
    assert warnings, "expected a WARNING from axm_audit.core.rules.security"
    msg = warnings[0].getMessage()
    assert "rc=1" in msg or "1" in msg


def test_bandit_rc1_valid_json_no_warn(monkeypatch, caplog):
    payload = '{"results": [{"issue_severity": "HIGH", "issue_text": "x"}]}'
    monkeypatch.setattr(
        security_mod,
        "run_in_project",
        _fake_runner(returncode=1, stdout=payload, stderr=""),
    )
    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        result = run_bandit(Path("/tmp/src"), Path("/tmp"))

    assert "results" in result
    assert result["results"][0]["issue_severity"] == "HIGH"
    warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and r.name == _LOGGER_NAME
    ]
    assert not warnings


def test_bandit_rc0_no_warn(monkeypatch, caplog):
    monkeypatch.setattr(
        security_mod,
        "run_in_project",
        _fake_runner(returncode=0, stdout="", stderr=""),
    )
    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        result = run_bandit(Path("/tmp/src"), Path("/tmp"))

    assert result == {}
    warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and r.name == _LOGGER_NAME
    ]
    assert not warnings


def test_bandit_rc2_raises(monkeypatch):
    monkeypatch.setattr(
        security_mod,
        "run_in_project",
        _fake_runner(returncode=2, stdout="", stderr="bandit crashed"),
    )
    with pytest.raises(RuntimeError) as excinfo:
        run_bandit(Path("/tmp/src"), Path("/tmp"))

    msg = str(excinfo.value)
    assert "2" in msg
    assert "bandit crashed" in msg
