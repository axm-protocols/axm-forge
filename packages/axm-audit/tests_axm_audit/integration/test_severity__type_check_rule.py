"""Integration tests for TypeCheckRule severity escalation on env-incompleteness."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from axm_audit.core.rules.quality_rules import TypeCheckRule
from axm_audit.models.results import Severity


def _mypy_json_line(
    file: str, line: int, message: str, code: str, severity: str = "error"
) -> str:
    return json.dumps(
        {
            "file": file,
            "line": line,
            "message": message,
            "code": code,
            "severity": severity,
        }
    )


@pytest.fixture()
def rule() -> TypeCheckRule:
    return TypeCheckRule()


@pytest.fixture()
def _patch_infra(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Patch run_in_project and _get_audit_targets so check() doesn't run mypy."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    monkeypatch.setattr(
        "axm_audit.core.rules.quality_rules._get_audit_targets",
        lambda p: (["src"], ["src"]),
    )
    return tmp_path


def _patch_check_src_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(TypeCheckRule, "check_src", lambda self, p: None)


def _mock_mypy_full(
    monkeypatch: pytest.MonkeyPatch, *, stdout: str, returncode: int, stderr: str = ""
) -> None:
    """Mock run_in_project with full control over stdout/stderr/returncode."""
    proc = MagicMock(stdout=stdout, stderr=stderr, returncode=returncode)
    monkeypatch.setattr(
        "axm_audit.core.rules.quality_rules.run_in_project",
        lambda *a, **kw: proc,
    )


def test_missing_stub_masking_fails(
    rule: TypeCheckRule,
    monkeypatch: pytest.MonkeyPatch,
    _patch_infra: Path,
) -> None:
    """AC1, AC5: a missing-stub signal must yield a FAILING result (not 100),
    naming the offending lib + remediation. Reproduces AXM-1878 masking."""
    _patch_check_src_ok(monkeypatch)
    stdout = _mypy_json_line(
        "src/mod.py",
        1,
        'Library stubs not installed for "jsonschema"',
        "import-untyped",
    )
    _mock_mypy_full(monkeypatch, stdout=stdout, returncode=1)

    result = rule.check(_patch_infra)

    assert result.passed is False
    assert result.score is not None and result.score < 100
    assert "jsonschema" in result.message
    assert result.severity is Severity.ERROR


def test_import_not_found_masking_fails(
    rule: TypeCheckRule,
    monkeypatch: pytest.MonkeyPatch,
    _patch_infra: Path,
) -> None:
    """AC1: an [import-not-found] error (env missing a dependency) fails loud."""
    _patch_check_src_ok(monkeypatch)
    stdout = _mypy_json_line(
        "src/mod.py",
        1,
        'Cannot find implementation or library stub for module named "axm_protocols"',
        "import-not-found",
    )
    _mock_mypy_full(monkeypatch, stdout=stdout, returncode=1)

    result = rule.check(_patch_infra)

    assert result.passed is False
    assert result.severity is Severity.ERROR


def test_blocking_exit_code_2_never_passes(
    rule: TypeCheckRule,
    monkeypatch: pytest.MonkeyPatch,
    _patch_infra: Path,
) -> None:
    """AC2: a blocking mypy exit (code 2) with non-JSON stdout must NOT map
    to a 100 — the truncated/aborted run is surfaced as a failure."""
    _patch_check_src_ok(monkeypatch)
    # Blocking errors come as plain text mypy can't express as JSON entries.
    stdout = "src/broken.py:1: error: unexpected EOF while parsing  [syntax]\n"
    _mock_mypy_full(monkeypatch, stdout=stdout, returncode=2)

    result = rule.check(_patch_infra)

    assert result.passed is False
    assert result.score != 100
    assert result.severity is Severity.ERROR
