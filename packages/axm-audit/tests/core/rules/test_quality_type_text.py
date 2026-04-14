from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from axm_audit.core.rules.quality import TypeCheckRule


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
        "axm_audit.core.rules.quality._get_audit_targets",
        lambda p: (["src"], ["src"]),
    )
    return tmp_path


def _mock_mypy(monkeypatch: pytest.MonkeyPatch, stdout: str) -> None:
    proc = MagicMock(stdout=stdout, returncode=1)
    monkeypatch.setattr(
        "axm_audit.core.rules.quality.run_in_project",
        lambda *a, **kw: proc,
    )


def _patch_check_src_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(TypeCheckRule, "check_src", lambda self, p: None)


# ── Unit tests ──────────────────────────────────────────────────────


def test_type_check_text_no_padding(
    rule: TypeCheckRule,
    monkeypatch: pytest.MonkeyPatch,
    _patch_infra: Path,
) -> None:
    """text lines start with '\u2022' not '     \u2022'."""
    _patch_check_src_ok(monkeypatch)
    stdout = "\n".join(
        [
            _mypy_json_line("pkg/mod.py", 10, "Incompatible types", "assignment"),
            _mypy_json_line("pkg/mod.py", 20, "Missing return", "return"),
        ]
    )
    _mock_mypy(monkeypatch, stdout)

    result = rule.check(_patch_infra)

    assert result.text is not None
    for line in result.text.splitlines():
        assert line.startswith("\u2022"), f"Line has unexpected padding: {line!r}"
        assert not line.startswith("     "), f"Line has 5-space padding: {line!r}"


def test_type_check_text_strips_src_prefix(
    rule: TypeCheckRule,
    monkeypatch: pytest.MonkeyPatch,
    _patch_infra: Path,
) -> None:
    """Paths under src/ have the prefix stripped in text."""
    _patch_check_src_ok(monkeypatch)
    stdout = _mypy_json_line("src/pkg/mod.py", 5, "Bad type", "arg-type")
    _mock_mypy(monkeypatch, stdout)

    result = rule.check(_patch_infra)

    assert result.text is not None
    assert "pkg/mod.py:" in result.text
    assert "src/pkg/mod.py:" not in result.text


def test_type_check_tests_path_unchanged(
    rule: TypeCheckRule,
    monkeypatch: pytest.MonkeyPatch,
    _patch_infra: Path,
) -> None:
    """Paths under tests/ are kept as-is in text."""
    _patch_check_src_ok(monkeypatch)
    stdout = _mypy_json_line("tests/test_x.py", 3, "Bad arg", "arg-type")
    _mock_mypy(monkeypatch, stdout)

    result = rule.check(_patch_infra)

    assert result.text is not None
    assert "tests/test_x.py:" in result.text


# ── Edge cases ──────────────────────────────────────────────────────


def test_type_check_path_outside_src_tests_unchanged(
    rule: TypeCheckRule,
    monkeypatch: pytest.MonkeyPatch,
    _patch_infra: Path,
) -> None:
    """Paths not under src/ or tests/ stay unchanged."""
    _patch_check_src_ok(monkeypatch)
    stdout = _mypy_json_line("scripts/deploy.py", 1, "Name error", "name-defined")
    _mock_mypy(monkeypatch, stdout)

    result = rule.check(_patch_infra)

    assert result.text is not None
    assert "scripts/deploy.py:" in result.text


def test_type_check_empty_stdout(
    rule: TypeCheckRule,
    monkeypatch: pytest.MonkeyPatch,
    _patch_infra: Path,
) -> None:
    """Empty mypy stdout produces text=None and empty errors."""
    _patch_check_src_ok(monkeypatch)
    _mock_mypy(monkeypatch, "")

    result = rule.check(_patch_infra)

    assert result.text is None
    assert result.details is not None
    assert result.details["errors"] == []


def test_type_check_zero_errors(
    rule: TypeCheckRule,
    monkeypatch: pytest.MonkeyPatch,
    _patch_infra: Path,
) -> None:
    """Zero errors means text=None and passed=True."""
    _patch_check_src_ok(monkeypatch)
    _mock_mypy(monkeypatch, "")

    result = rule.check(_patch_infra)

    assert result.text is None
    assert result.passed is True
