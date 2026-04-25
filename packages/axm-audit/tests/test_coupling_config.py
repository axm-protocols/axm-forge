from __future__ import annotations

import textwrap
from pathlib import Path

from axm_audit.core.rules.architecture import CouplingMetricRule
from axm_audit.core.rules.architecture.coupling import (
    build_coupling_result,
    read_coupling_config,
)

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

    # Generate unique stdlib imports so fan-out == n_imports
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
    ]
    lines = [f"import {m}" for m in stdlib_modules[:n_imports]]
    lines.append("\nx = 1\n")
    (src / f"{module}.py").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Unit tests — read_coupling_config
# ---------------------------------------------------------------------------


def test_read_coupling_config_defaults(tmp_path: Path) -> None:
    """No pyproject.toml → default threshold 10, empty overrides."""
    threshold, overrides, _bonus, _multiplier = read_coupling_config(tmp_path)
    assert threshold == 10
    assert overrides == {}


def test_read_coupling_config_custom_threshold(tmp_path: Path) -> None:
    _write_pyproject(
        tmp_path,
        """\
        [tool.axm-audit.coupling]
        fan_out_threshold = 15
    """,
    )
    threshold, overrides, _bonus, _multiplier = read_coupling_config(tmp_path)
    assert threshold == 15
    assert overrides == {}


def test_read_coupling_config_with_overrides(tmp_path: Path) -> None:
    _write_pyproject(
        tmp_path,
        """\
        [tool.axm-audit.coupling]
        [tool.axm-audit.coupling.overrides]
        "rules.quality" = 20
    """,
    )
    threshold, overrides, _bonus, _multiplier = read_coupling_config(tmp_path)
    assert threshold == 10
    assert overrides == {"rules.quality": 20}


def test_read_coupling_config_invalid_threshold(tmp_path: Path) -> None:
    _write_pyproject(
        tmp_path,
        """\
        [tool.axm-audit.coupling]
        fan_out_threshold = "not_a_number"
    """,
    )
    threshold, overrides, _bonus, _multiplier = read_coupling_config(tmp_path)
    assert threshold == 10
    assert overrides == {}


def test_read_coupling_config_negative_threshold(tmp_path: Path) -> None:
    _write_pyproject(
        tmp_path,
        """\
        [tool.axm-audit.coupling]
        fan_out_threshold = -5
    """,
    )
    threshold, overrides, _bonus, _multiplier = read_coupling_config(tmp_path)
    assert threshold == 10
    assert overrides == {}


def test_read_coupling_config_invalid_override_value(tmp_path: Path) -> None:
    _write_pyproject(
        tmp_path,
        """\
        [tool.axm-audit.coupling]
        [tool.axm-audit.coupling.overrides]
        "mod" = "bad"
    """,
    )
    threshold, overrides, _bonus, _multiplier = read_coupling_config(tmp_path)
    assert threshold == 10
    assert overrides == {}


# ---------------------------------------------------------------------------
# Unit test — build_coupling_result with overrides
# ---------------------------------------------------------------------------


def test_build_coupling_result_with_overrides() -> None:
    fan_out = {"mod_a": 11, "mod_b": 11}
    fan_in = {"mod_a": 2, "mod_b": 3}
    overrides = {"mod_a": 15}
    threshold = 10

    result = build_coupling_result(fan_out, fan_in, threshold, overrides)

    over_names = [entry["module"] for entry in result["over_threshold"]]
    assert "mod_b" in over_names
    assert "mod_a" not in over_names
    assert result["n_over_threshold"] == 1


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


def test_coupling_rule_reads_pyproject_config(tmp_path: Path) -> None:
    """Module with fan-out=15 passes when pyproject sets threshold=20."""
    _write_pyproject(
        tmp_path,
        """\
        [project]
        name = "fakepkg"

        [tool.axm-audit.coupling]
        fan_out_threshold = 20
    """,
    )
    _make_src_module(tmp_path, "fakepkg", "heavy", n_imports=15)

    rule = CouplingMetricRule()
    result = rule.check(tmp_path)
    assert result.passed is True


def test_coupling_rule_per_module_override(tmp_path: Path) -> None:
    """Per-module override lets a specific module exceed base threshold."""
    _write_pyproject(
        tmp_path,
        """\
        [project]
        name = "fakepkg"

        [tool.axm-audit.coupling]
        fan_out_threshold = 5
        [tool.axm-audit.coupling.overrides]
        "rules.quality" = 15
    """,
    )
    # Create the overridden module at the dotted path rules/quality.py
    src = tmp_path / "src" / "fakepkg" / "rules"
    src.mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "fakepkg" / "__init__.py").write_text("", encoding="utf-8")
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
    ]
    lines = [f"import {m}" for m in stdlib_modules]  # 11 imports
    lines.append("\nx = 1\n")
    (src / "quality.py").write_text("\n".join(lines), encoding="utf-8")

    rule = CouplingMetricRule()
    result = rule.check(tmp_path)
    # fan-out=11, base threshold=5 would fail, but override=15 lets it pass
    assert result.passed is True


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_read_coupling_config_missing_audit_section(tmp_path: Path) -> None:
    """pyproject.toml exists but has no [tool.axm-audit] section."""
    _write_pyproject(
        tmp_path,
        """\
        [project]
        name = "somepkg"
    """,
    )
    threshold, overrides, _bonus, _multiplier = read_coupling_config(tmp_path)
    assert threshold == 10
    assert overrides == {}


def test_read_coupling_config_malformed_toml(tmp_path: Path) -> None:
    """Invalid TOML syntax → fallback to defaults, no crash."""
    (tmp_path / "pyproject.toml").write_text(
        "[invalid toml\nno closing bracket",
        encoding="utf-8",
    )
    threshold, overrides, _bonus, _multiplier = read_coupling_config(tmp_path)
    assert threshold == 10
    assert overrides == {}


def test_read_coupling_config_override_nonexistent_module(tmp_path: Path) -> None:
    """Override for a module that doesn't exist is silently kept in dict."""
    _write_pyproject(
        tmp_path,
        """\
        [tool.axm-audit.coupling]
        [tool.axm-audit.coupling.overrides]
        "no.such.module" = 25
    """,
    )
    threshold, overrides, _bonus, _multiplier = read_coupling_config(tmp_path)
    assert threshold == 10
    assert overrides == {"no.such.module": 25}


def test_read_coupling_config_empty_overrides(tmp_path: Path) -> None:
    """Empty overrides table → empty dict, base threshold applies."""
    _write_pyproject(
        tmp_path,
        """\
        [tool.axm-audit.coupling]
        fan_out_threshold = 12
        [tool.axm-audit.coupling.overrides]
    """,
    )
    threshold, overrides, _bonus, _multiplier = read_coupling_config(tmp_path)
    assert threshold == 12
    assert overrides == {}
