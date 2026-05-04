from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from axm_audit.core.rules import security as security_mod
from axm_audit.core.rules.security import _run_bandit

_LOGGER_NAME = "axm_audit.core.rules.security"


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
        result = _run_bandit(Path("/tmp/src"), Path("/tmp"))

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
        result = _run_bandit(Path("/tmp/src"), Path("/tmp"))

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
        result = _run_bandit(Path("/tmp/src"), Path("/tmp"))

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
        _run_bandit(Path("/tmp/src"), Path("/tmp"))

    msg = str(excinfo.value)
    assert "2" in msg
    assert "bandit crashed" in msg
