"""Tests for tiered severity in coupling findings (AXM-1293)."""

from __future__ import annotations

import textwrap
from pathlib import Path

from axm_audit.core.rules.architecture import CouplingMetricRule
from axm_audit.core.rules.architecture.coupling import (
    read_coupling_config,
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


class TestIntegrationScope:
    """Integration-scope tests (real filesystem I/O, public API)."""

    def test_passed_true_with_warnings_only(self, tmp_path: Path) -> None:
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

    def test_passed_false_with_error(self, tmp_path: Path) -> None:
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

    def test_multiplier_from_config(self, tmp_path: Path) -> None:
        """severity_error_multiplier=3 from pyproject.toml."""
        _write_pyproject(
            tmp_path,
            """\
            [tool.axm-audit.coupling]
            fan_out_threshold = 10
            severity_error_multiplier = 3
        """,
        )
        _threshold, _overrides, _bonus, multiplier = read_coupling_config(tmp_path)
        assert multiplier == 3

    def test_multiplier_default(self, tmp_path: Path) -> None:
        """No config → default multiplier=2."""
        _threshold, _overrides, _bonus, multiplier = read_coupling_config(tmp_path)
        assert multiplier == 2

    def test_multiplier_minimum_1(self, tmp_path: Path) -> None:
        """severity_error_multiplier=0 → falls back to 1 (same as no tiers)."""
        _write_pyproject(
            tmp_path,
            """\
            [tool.axm-audit.coupling]
            severity_error_multiplier = 0
        """,
        )
        _threshold, _overrides, _bonus, multiplier = read_coupling_config(tmp_path)
        assert multiplier == 1

    def test_mixed_severities_functional(self, tmp_path: Path) -> None:
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

    def test_scoring_differentiation_functional(self, tmp_path: Path) -> None:
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
        assert result.score == 89  # 100 - (2*3 + 1*5)
