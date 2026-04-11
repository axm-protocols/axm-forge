"""Tests for tiered severity in coupling findings (AXM-1293)."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from axm_audit.core.rules.architecture import (
    CouplingMetricRule,
    _build_coupling_result,
    _read_coupling_config,
)
from axm_audit.models.results import Severity

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_pyproject(tmp_path: Path, content: str) -> None:
    """Write a pyproject.toml into *tmp_path*."""
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent(content),
        encoding="utf-8",
    )


def _make_src_module(
    tmp_path: Path,
    pkg: str,
    module: str,
    n_imports: int,
) -> None:
    """Create a source module that imports *n_imports* stdlib modules."""
    src = tmp_path / "src" / pkg
    src.mkdir(parents=True, exist_ok=True)
    (src / "__init__.py").write_text("", encoding="utf-8")

    stdlib_modules = [
        "os",
        "sys",
        "json",
        "re",
        "math",
        "io",
        "csv",
        "ast",
        "copy",
        "time",
        "uuid",
        "enum",
        "types",
        "shutil",
        "string",
        "random",
        "hashlib",
        "logging",
        "pathlib",
        "textwrap",
        "functools",
        "itertools",
        "collections",
        "contextlib",
        "dataclasses",
        "operator",
        "struct",
        "socket",
        "signal",
        "threading",
        "subprocess",
    ]
    lines = [f"import {m}" for m in stdlib_modules[:n_imports]]
    lines.append("\nx = 1\n")
    (src / f"{module}.py").write_text("\n".join(lines), encoding="utf-8")


def _build_result(
    modules: dict[str, int],
    threshold: int = 10,
    severity_error_multiplier: int = 2,
) -> dict[str, Any]:
    """Shortcut to call _build_coupling_result with simple fan-out dict."""
    fan_in = dict.fromkeys(modules, 1)
    return _build_coupling_result(
        fan_out=modules,
        fan_in=fan_in,
        threshold=threshold,
        severity_error_multiplier=severity_error_multiplier,
    )


# ---------------------------------------------------------------------------
# Unit tests — per-module severity in _build_coupling_result
# ---------------------------------------------------------------------------


def test_warning_severity_borderline() -> None:
    """Module fan-out=12, threshold=10, multiplier=2 → severity warning."""
    result = _build_result({"mod_a": 12}, threshold=10, severity_error_multiplier=2)

    assert result["n_over_threshold"] == 1
    entry = result["over_threshold"][0]
    assert entry["severity"] == "warning"


def test_error_severity_extreme() -> None:
    """Module fan-out=25, threshold=10, multiplier=2 → severity error."""
    result = _build_result({"mod_a": 25}, threshold=10, severity_error_multiplier=2)

    assert result["n_over_threshold"] == 1
    entry = result["over_threshold"][0]
    assert entry["severity"] == "error"


def test_passed_true_with_warnings_only(tmp_path: Path) -> None:
    """One module at warning level, none at error → passed=True."""
    _write_pyproject(
        tmp_path,
        """\
        [project]
        name = "fakepkg"

        [tool.axm-audit.coupling]
        fan_out_threshold = 10
    """,
    )
    # fan-out=12 with threshold=10, multiplier=2 → warning (12 <= 20)
    _make_src_module(tmp_path, "fakepkg", "borderline", n_imports=12)

    rule = CouplingMetricRule()
    result = rule.check(tmp_path)
    assert result.passed is True


def test_passed_false_with_error(tmp_path: Path) -> None:
    """One module at error level → passed=False."""
    _write_pyproject(
        tmp_path,
        """\
        [project]
        name = "fakepkg"

        [tool.axm-audit.coupling]
        fan_out_threshold = 10
    """,
    )
    # fan-out=25 with threshold=10, multiplier=2 → error (25 > 20)
    _make_src_module(tmp_path, "fakepkg", "extreme", n_imports=25)

    rule = CouplingMetricRule()
    result = rule.check(tmp_path)
    assert result.passed is False


# ---------------------------------------------------------------------------
# Unit tests — multiplier config
# ---------------------------------------------------------------------------


def test_multiplier_from_config(tmp_path: Path) -> None:
    """severity_error_multiplier=3 from pyproject.toml."""
    _write_pyproject(
        tmp_path,
        """\
        [tool.axm-audit.coupling]
        fan_out_threshold = 10
        severity_error_multiplier = 3
    """,
    )
    _threshold, _overrides, _bonus, multiplier = _read_coupling_config(tmp_path)
    assert multiplier == 3


def test_multiplier_default(tmp_path: Path) -> None:
    """No config → default multiplier=2."""
    _threshold, _overrides, _bonus, multiplier = _read_coupling_config(tmp_path)
    assert multiplier == 2


def test_multiplier_minimum_1(tmp_path: Path) -> None:
    """severity_error_multiplier=0 → falls back to 1 (same as no tiers)."""
    _write_pyproject(
        tmp_path,
        """\
        [tool.axm-audit.coupling]
        severity_error_multiplier = 0
    """,
    )
    _threshold, _overrides, _bonus, multiplier = _read_coupling_config(tmp_path)
    assert multiplier == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_multiplier_1_all_error() -> None:
    """multiplier=1 → all over-threshold modules are immediately ERROR."""
    result = _build_result(
        {"mod_a": 11, "mod_b": 15},
        threshold=10,
        severity_error_multiplier=1,
    )

    assert result["n_over_threshold"] == 2
    for entry in result["over_threshold"]:
        assert entry["severity"] == "error"


def test_mixed_severities() -> None:
    """Module A at warning, Module B at error → worst severity, passed=False."""
    # threshold=10, multiplier=2 → warning at 11-20, error at 21+
    result = _build_result(
        {"mod_a": 12, "mod_b": 25, "mod_c": 5},
        threshold=10,
        severity_error_multiplier=2,
    )

    over = result["over_threshold"]
    assert len(over) == 2

    severities = {e["module"]: e["severity"] for e in over}
    assert severities["mod_a"] == "warning"
    assert severities["mod_b"] == "error"


def test_mixed_severities_functional(tmp_path: Path) -> None:
    """Functional: mixed severities → result severity=ERROR, passed=False."""
    _write_pyproject(
        tmp_path,
        """\
        [project]
        name = "fakepkg"

        [tool.axm-audit.coupling]
        fan_out_threshold = 10
    """,
    )
    # warning-level module (12 imports, threshold=10, multiplier=2 → 12 <= 20)
    _make_src_module(tmp_path, "fakepkg", "warn_mod", n_imports=12)
    # error-level module (25 imports → 25 > 20)
    _make_src_module(tmp_path, "fakepkg", "err_mod", n_imports=25)

    rule = CouplingMetricRule()
    result = rule.check(tmp_path)
    assert result.passed is False
    assert result.severity == Severity.ERROR


def test_scoring_differentiation() -> None:
    """2 warning + 1 error modules → score = 100 - (2x3 + 1x5) = 89."""
    # threshold=10, multiplier=2
    # mod_a=12 (warning), mod_b=15 (warning), mod_c=25 (error)
    result = _build_result(
        {"mod_a": 12, "mod_b": 15, "mod_c": 25, "mod_d": 5},
        threshold=10,
        severity_error_multiplier=2,
    )

    over = result["over_threshold"]
    warnings = [e for e in over if e["severity"] == "warning"]
    errors = [e for e in over if e["severity"] == "error"]
    assert len(warnings) == 2
    assert len(errors) == 1


def test_scoring_differentiation_functional(tmp_path: Path) -> None:
    """Functional: 2 warning + 1 error → score = 100 - (2x3 + 1x5) = 89."""
    _write_pyproject(
        tmp_path,
        """\
        [project]
        name = "fakepkg"

        [tool.axm-audit.coupling]
        fan_out_threshold = 10
    """,
    )
    _make_src_module(tmp_path, "fakepkg", "warn_a", n_imports=12)
    _make_src_module(tmp_path, "fakepkg", "warn_b", n_imports=15)
    _make_src_module(tmp_path, "fakepkg", "err_c", n_imports=25)

    rule = CouplingMetricRule()
    result = rule.check(tmp_path)
    assert result.details is not None
    assert result.details["score"] == 89  # 100 - (2*3 + 1*5)
