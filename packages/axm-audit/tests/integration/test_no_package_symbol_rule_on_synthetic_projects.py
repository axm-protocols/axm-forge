"""Integration tests for NoPackageSymbolRule on synthetic project layouts.

These tests materialize a minimal package on tmp_path (src/, tests/,
pyproject.toml) and run the full rule end-to-end.  They cover verdict
logic (AC3, AC4, AC5), severity/score/payload shape (AC6), opt-out
markers (AC7), and the unit-tier skip (AC8).

In-memory AST tests for the criterion detectors live alongside the rule
implementation under ``tests/unit/core/rules/test_quality/``.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from axm_audit.core.rules.base import Severity
from axm_audit.core.rules.test_quality.no_package_symbol import (
    NoPackageSymbolRule,
)

pytestmark = pytest.mark.integration


def _write_pkg(tmp_path: Path, *, script_name: str = "pkg-cli") -> Path:
    """Lay out a minimal package with src/pkg + tests/ + [project.scripts]."""
    pkg_root = tmp_path / "pkg-proj"
    (pkg_root / "src" / "pkg" / "core").mkdir(parents=True)
    (pkg_root / "src" / "pkg" / "__init__.py").write_text("")
    (pkg_root / "src" / "pkg" / "core" / "__init__.py").write_text("")
    (pkg_root / "src" / "pkg" / "core" / "mod.py").write_text(
        "def fn() -> int:\n    return 1\n\nclass Rule:\n    pass\n"
    )
    (pkg_root / "tests").mkdir()
    (pkg_root / "tests" / "unit").mkdir()
    (pkg_root / "tests" / "integration").mkdir()
    (pkg_root / "tests" / "e2e").mkdir()
    (pkg_root / "pyproject.toml").write_text(
        textwrap.dedent(
            f"""
            [project]
            name = "pkg"
            version = "0.0.0"

            [project.scripts]
            {script_name} = "pkg.cli:main"
            """
        ).strip()
    )
    return pkg_root


# ----------------------------------------------------------------------
# AC3, AC4, AC5 — verdict logic via the full rule
# ----------------------------------------------------------------------


_BODY_A_ONLY = "from pkg.core.mod import fn\n\ndef test_x():\n    assert fn() == 1\n"
_BODY_B_ONLY = (
    "import subprocess\n\n"
    "def test_x():\n"
    '    subprocess.run(["pkg-cli", "do"], check=True)\n'
)
_BODY_BOTH = (
    "import subprocess\n"
    "from pkg.core.mod import fn\n\n"
    "def test_x():\n"
    "    fn()\n"
    '    subprocess.run(["pkg-cli", "do"], check=True)\n'
)


@pytest.mark.parametrize(
    "body",
    [_BODY_A_ONLY, _BODY_B_ONLY, _BODY_BOTH],
    ids=["a-only", "b-only", "both"],
)
def test_verdict_ok_when_either_criterion_passes(tmp_path: Path, body: str) -> None:
    """AC3: at least one criterion -> no finding in tests/integration/."""
    pkg_root = _write_pkg(tmp_path)
    (pkg_root / "tests" / "integration" / "test_x.py").write_text(body)
    rule = NoPackageSymbolRule()
    result = rule.check(pkg_root)
    assert result.passed is True
    assert result.details["findings"] == []


def test_verdict_mislocated_for_a_only_in_e2e_dir(tmp_path: Path) -> None:
    """AC4: (a)-pass-(b)-fail in tests/e2e/ -> MISLOCATED_INTEGRATION."""
    pkg_root = _write_pkg(tmp_path)
    (pkg_root / "tests" / "e2e" / "test_x.py").write_text(
        "from pkg.core.mod import fn\n\ndef test_x():\n    assert fn() == 1\n"
    )
    rule = NoPackageSymbolRule()
    result = rule.check(pkg_root)
    assert result.passed is False
    findings = result.details["findings"]
    assert len(findings) == 1
    assert findings[0]["verdict"] == "MISLOCATED_INTEGRATION"
    assert "tests/integration/" in (result.fix_hint or "")


def test_verdict_no_symbol_when_both_fail(tmp_path: Path) -> None:
    """AC5: neither criterion in tests/integration/ -> NO_PACKAGE_SYMBOL."""
    pkg_root = _write_pkg(tmp_path)
    (pkg_root / "tests" / "integration" / "test_x.py").write_text(
        "from pathlib import Path\n\n"
        "def test_x(tmp_path):\n"
        "    Path(tmp_path / 'README.md').write_text('hi')\n"
        "    assert (tmp_path / 'README.md').read_text() == 'hi'\n"
    )
    rule = NoPackageSymbolRule()
    result = rule.check(pkg_root)
    assert result.passed is False
    findings = result.details["findings"]
    assert len(findings) == 1
    assert findings[0]["verdict"] == "NO_PACKAGE_SYMBOL"
    hint = result.fix_hint or ""
    assert "versioned rule" in hint or "linter" in hint


# ----------------------------------------------------------------------
# AC6 — severity / score / payload shape
# ----------------------------------------------------------------------


def test_severity_and_score(tmp_path: Path) -> None:
    """AC6: one finding -> severity=WARNING, score=98."""
    pkg_root = _write_pkg(tmp_path)
    (pkg_root / "tests" / "integration" / "test_x.py").write_text(
        "def test_x():\n    assert 1 + 1 == 2\n"
    )
    rule = NoPackageSymbolRule()
    result = rule.check(pkg_root)
    assert result.severity == Severity.WARNING
    assert result.score == 98


def test_score_floors_at_zero(tmp_path: Path) -> None:
    """AC6: score never drops below 0 even with many findings."""
    pkg_root = _write_pkg(tmp_path)
    for i in range(60):
        (pkg_root / "tests" / "integration" / f"test_x_{i}.py").write_text(
            "def test_x():\n    assert 1 + 1 == 2\n"
        )
    rule = NoPackageSymbolRule()
    result = rule.check(pkg_root)
    assert result.score == 0


def test_findings_payload_shape(tmp_path: Path) -> None:
    """AC6: every finding has the documented keys."""
    pkg_root = _write_pkg(tmp_path)
    (pkg_root / "tests" / "integration" / "test_x.py").write_text(
        "def test_x():\n    assert 1 + 1 == 2\n"
    )
    rule = NoPackageSymbolRule()
    result = rule.check(pkg_root)
    findings = result.details["findings"]
    assert len(findings) == 1
    finding = findings[0]
    for key in ("test_file", "verdict", "criterion_a_passed", "criterion_b_passed"):
        assert key in finding, f"missing key: {key}"


# ----------------------------------------------------------------------
# AC7 — opt-out markers
# ----------------------------------------------------------------------


def test_marker_no_package_symbol_ok_skips_file(tmp_path: Path) -> None:
    """AC7: file-level `pytestmark = pytest.mark.no_package_symbol_ok` skips."""
    pkg_root = _write_pkg(tmp_path)
    (pkg_root / "tests" / "integration" / "test_x.py").write_text(
        "import pytest\n"
        "pytestmark = pytest.mark.no_package_symbol_ok\n\n"
        "def test_x():\n    assert 1 + 1 == 2\n"
    )
    rule = NoPackageSymbolRule()
    result = rule.check(pkg_root)
    assert result.passed is True
    assert result.details["findings"] == []


def test_marker_no_package_symbol_ok_per_test(tmp_path: Path) -> None:
    """AC7: per-test marker excludes only the marked test."""
    pkg_root = _write_pkg(tmp_path)
    (pkg_root / "tests" / "integration" / "test_x.py").write_text(
        "import pytest\n\n"
        "@pytest.mark.no_package_symbol_ok\n"
        "def test_x():\n    assert 1 + 1 == 2\n\n"
        "def test_y():\n    assert 2 + 2 == 4\n"
    )
    rule = NoPackageSymbolRule()
    result = rule.check(pkg_root)
    findings = result.details["findings"]
    # test_x is opted out, test_y still has no symbol/script -> 1 finding max.
    assert len(findings) <= 1


# ----------------------------------------------------------------------
# AC8 — unit tier is skipped
# ----------------------------------------------------------------------


def test_unit_tier_is_skipped(tmp_path: Path) -> None:
    """AC8: offenders under tests/unit/ never produce findings."""
    pkg_root = _write_pkg(tmp_path)
    (pkg_root / "tests" / "unit" / "test_x.py").write_text(
        "def test_x():\n    assert 1 + 1 == 2\n"
    )
    rule = NoPackageSymbolRule()
    result = rule.check(pkg_root)
    assert result.passed is True
    assert result.details["findings"] == []
