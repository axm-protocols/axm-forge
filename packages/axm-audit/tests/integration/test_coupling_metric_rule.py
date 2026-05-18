"""Split from ``test_architecture.py``."""

import textwrap
from pathlib import Path
from typing import Any

import pytest

from axm_audit.core.rules.architecture import CouplingMetricRule, GodClassRule
from tests.integration._helpers import _make_src_module__from_coupling_severity


@pytest.fixture()
def rule() -> GodClassRule:
    return GodClassRule()


class TestCouplingMetricRuleIO:
    """Tests for CouplingMetricRule that touch the filesystem."""

    def test_low_coupling_passes(self, tmp_path: Path) -> None:
        """Low coupling project passes."""
        from axm_audit.core.rules.architecture import CouplingMetricRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        (src / "a.py").write_text("x = 1\n")
        (src / "b.py").write_text("y = 2\n")

        rule = CouplingMetricRule()
        result = rule.check(tmp_path)
        assert result.passed is True

    def test_detects_high_coupling(self, tmp_path: Path) -> None:
        """Flags module with many imports (high fan-out)."""
        from axm_audit.core.rules.architecture import CouplingMetricRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        # Create many distinct modules
        for i in range(15):
            (src / f"mod_{i}.py").write_text(f"val_{i} = {i}\n")
        # Create hub module that imports all (distinct module names)
        imports = "\n".join(f"import mod_{i}" for i in range(15))
        (src / "hub.py").write_text(imports)

        rule = CouplingMetricRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["max_fan_out"] >= 10
        assert result.details["n_over_threshold"] >= 1


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
    _make_src_module__from_coupling_severity(
        tmp_path, "fakepkg", "borderline", n_imports=12
    )

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
    _make_src_module__from_coupling_severity(
        tmp_path, "fakepkg", "extreme", n_imports=25
    )

    rule = CouplingMetricRule()
    result = rule.check(tmp_path)
    assert result.passed is False


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
    _make_src_module__from_coupling_severity(
        tmp_path, "fakepkg", "warn_a", n_imports=12
    )
    _make_src_module__from_coupling_severity(
        tmp_path, "fakepkg", "warn_b", n_imports=15
    )
    _make_src_module__from_coupling_severity(tmp_path, "fakepkg", "err_c", n_imports=25)

    rule = CouplingMetricRule()
    result = rule.check(tmp_path)
    assert result.details is not None
    assert result.score == 89  # 100 - (2*3 + 1*5)


@pytest.mark.integration
class TestCouplingFormula:
    """Tests for the new coupling scoring formula."""

    def test_all_below_threshold(self, tmp_path: Path) -> None:
        """All modules below threshold → score=100, n_over=0."""
        from axm_audit.core.rules.architecture import CouplingMetricRule

        rule = CouplingMetricRule(fan_out_threshold=10)
        src = tmp_path / "src" / "pkg"
        src.mkdir(parents=True)

        # Create 3 modules with < 10 imports each
        for name, n_imports in [("a", 3), ("b", 5), ("c", 8)]:
            imports = "\n".join(f"import mod_{i}" for i in range(n_imports))
            (src / f"{name}.py").write_text(imports)
        (src / "__init__.py").write_text("")

        result = rule.check(tmp_path)
        assert result.details is not None
        score = result.score
        assert score == 100
        assert result.details["n_over_threshold"] == 0

    def test_some_above_threshold(self, tmp_path: Path) -> None:
        """2 modules above threshold (both warnings) → score=94."""
        from axm_audit.core.rules.architecture import CouplingMetricRule

        rule = CouplingMetricRule(fan_out_threshold=10)
        src = tmp_path / "src" / "pkg"
        src.mkdir(parents=True)

        # a=5 (under), b=12 (warning), c=15 (warning)
        # default multiplier=2 → error threshold=20, both under
        (src / "a.py").write_text("\n".join(f"import m{i}" for i in range(5)))
        (src / "b.py").write_text("\n".join(f"import m{i}" for i in range(12)))
        (src / "c.py").write_text("\n".join(f"import m{i}" for i in range(15)))
        (src / "__init__.py").write_text("")

        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["n_over_threshold"] == 2
        assert result.score == 94  # 100 - 2*3 (warnings)

    def test_many_above_threshold_floors_at_zero(self, tmp_path: Path) -> None:
        """Many modules above threshold → score floors at 0."""
        from axm_audit.core.rules.architecture import CouplingMetricRule

        rule = CouplingMetricRule(fan_out_threshold=10)
        src = tmp_path / "src" / "pkg"
        src.mkdir(parents=True)

        # fan-out=25, threshold=10, multiplier=2 → error threshold=20
        # 25 > 20 → all ERROR → 100 - 25*5 = 0 (floored)
        for i in range(25):
            (src / f"mod_{i}.py").write_text(
                "\n".join(f"import dep_{j}" for j in range(25))
            )
        (src / "__init__.py").write_text("")

        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.score == 0

    def test_no_src_returns_100(self, tmp_path: Path) -> None:
        """No src/ directory → score=100."""
        from axm_audit.core.rules.architecture import CouplingMetricRule

        rule = CouplingMetricRule()
        result = rule.check(tmp_path)
        assert result.score == 100

    def test_over_threshold_lists_modules(self, tmp_path: Path) -> None:
        """Details lists which modules exceed threshold."""
        from axm_audit.core.rules.architecture import CouplingMetricRule

        rule = CouplingMetricRule(fan_out_threshold=10)
        src = tmp_path / "src" / "pkg"
        src.mkdir(parents=True)

        (src / "ok.py").write_text("import os")
        (src / "big.py").write_text("\n".join(f"import m{i}" for i in range(15)))
        (src / "__init__.py").write_text("")

        result = rule.check(tmp_path)
        assert result.details is not None
        over = result.details["over_threshold"]
        assert len(over) == 1
        assert over[0]["fan_out"] == 15
        assert "big" in over[0]["module"]

    def test_init_py_excluded_from_coupling(self, tmp_path: Path) -> None:
        """__init__.py re-export files are exempt from fan-out analysis.

        Their purpose is to aggregate submodule exports, so high fan-out
        is structural — not a coupling smell.
        """
        from axm_audit.core.rules.architecture import CouplingMetricRule

        rule = CouplingMetricRule(fan_out_threshold=5)
        src = tmp_path / "src" / "pkg"
        src.mkdir(parents=True)

        # __init__.py with 10 re-exports — should be ignored
        init_imports = "\n".join(f"from pkg.sub_{i} import X{i}" for i in range(10))
        (src / "__init__.py").write_text(init_imports)

        # Regular module with 3 imports — under threshold
        (src / "core.py").write_text("import os\nimport sys\nimport json")

        result = rule.check(tmp_path)
        assert result.details is not None
        # __init__.py excluded → only core.py counted (3 imports, under 5)
        assert result.details["n_over_threshold"] == 0
        assert result.score == 100


_MOD = "axm_audit.core.rules.architecture"


_MOD_FROM_ROOT = "axm_audit.core.rules.architecture"


def _make_metrics(
    over: list[dict[str, Any]],
    *,
    max_fo: int = 18,
    max_fi: int = 5,
    avg: float = 6.5,
) -> dict[str, Any]:
    return {
        "max_fan_out": max_fo,
        "max_fan_in": max_fi,
        "avg_coupling": avg,
        "n_over_threshold": len(over),
        "over_threshold": over,
    }


def _patch_coupling(
    monkeypatch: pytest.MonkeyPatch,
    over: list[dict[str, Any]],
    *,
    n_warnings: int = 0,
    n_errors: int = 0,
    max_fo: int = 18,
) -> None:
    monkeypatch.setattr(
        f"{_MOD}.read_coupling_config",
        lambda _path: (12, {}, 0, 2),
    )
    monkeypatch.setattr(
        f"{_MOD}._compute_coupling_metrics",
        lambda *a, **kw: _make_metrics(over, max_fo=max_fo),
    )
    severity = "error" if n_errors else ("warning" if n_warnings else "info")
    monkeypatch.setattr(
        f"{_MOD}._resolve_coupling_severity",
        lambda _over: (n_warnings, n_errors, severity),
    )


@pytest.fixture()
def _src_dir(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    return tmp_path


def _make_over_entry_from_root(
    module: str,
    fan_out: int,
    effective_threshold: int,
    severity: str,
    role: str = "leaf",
) -> dict[str, Any]:
    return {
        "module": module,
        "fan_out": fan_out,
        "role": role,
        "effective_threshold": effective_threshold,
        "severity": severity,
    }


def _make_metrics_from_root(
    over: list[dict[str, Any]],
    *,
    max_fan_out: int = 20,
    max_fan_in: int = 5,
    avg_coupling: float = 8.0,
) -> dict[str, Any]:
    return {
        "max_fan_out": max_fan_out,
        "max_fan_in": max_fan_in,
        "avg_coupling": avg_coupling,
        "n_over_threshold": len(over),
        "over_threshold": over,
    }


@pytest.fixture()
def _patch_coupling_from_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    """Return a helper that patches coupling internals and runs check."""

    def _run(
        over: list[dict[str, Any]],
        n_warnings: int,
        n_errors: int,
        severity: str = "warning",
    ) -> Any:
        from axm_audit.core.rules.architecture import CouplingMetricRule

        metrics = _make_metrics_from_root(over)

        monkeypatch.setattr(
            f"{_MOD_FROM_ROOT}.read_coupling_config",
            lambda _p: (12, {}, 0, 2),
        )
        monkeypatch.setattr(
            f"{_MOD_FROM_ROOT}._compute_coupling_metrics",
            lambda *a, **kw: metrics,
        )
        monkeypatch.setattr(
            f"{_MOD_FROM_ROOT}._resolve_coupling_severity",
            lambda _o: (n_warnings, n_errors, severity),
        )

        # Ensure check_src returns None (no early exit)
        (tmp_path / "src").mkdir(exist_ok=True)
        monkeypatch.setattr(
            CouplingMetricRule,
            "check_src",
            lambda self, _p: None,
        )

        rule = CouplingMetricRule()
        return rule.check(tmp_path)

    return _run


class TestCouplingTextFormat:
    """AC1: text= lines use format '\u2022 {leaf} fo:{N}/{T} {symbol}'."""

    def test_coupling_text_format(
        self, monkeypatch: pytest.MonkeyPatch, _src_dir: Path
    ) -> None:
        over = [
            {
                "module": "axm_audit.core.rules.architecture",
                "fan_out": 18,
                "role": "leaf",
                "effective_threshold": 12,
                "severity": "warning",
            },
            {
                "module": "axm_audit.core.engine",
                "fan_out": 16,
                "role": "leaf",
                "effective_threshold": 12,
                "severity": "warning",
            },
            {
                "module": "axm_audit.formatters",
                "fan_out": 14,
                "role": "leaf",
                "effective_threshold": 10,
                "severity": "error",
            },
        ]
        _patch_coupling(monkeypatch, over, n_warnings=2, n_errors=1)

        rule = CouplingMetricRule()
        result = rule.check(_src_dir)

        assert result.text is not None
        lines = result.text.split("\n")
        assert len(lines) == 3
        assert lines[0] == "\u2022 architecture fo:18/12 \u26a0"
        assert lines[1] == "\u2022 engine fo:16/12 \u26a0"
        assert lines[2] == "\u2022 formatters fo:14/10 \u2718"

    def test_coupling_text_none_when_passed(
        self, monkeypatch: pytest.MonkeyPatch, _src_dir: Path
    ) -> None:
        _patch_coupling(monkeypatch, [], n_warnings=0, n_errors=0, max_fo=8)

        rule = CouplingMetricRule()
        result = rule.check(_src_dir)

        assert result.text is None


class TestCouplingTextEdgeCases:
    """Edge cases for text rendering."""

    def test_single_segment_module_name(
        self, monkeypatch: pytest.MonkeyPatch, _src_dir: Path
    ) -> None:
        """Module name without dots — rsplit returns the name unchanged."""
        over = [
            {
                "module": "utils",
                "fan_out": 15,
                "role": "leaf",
                "effective_threshold": 12,
                "severity": "warning",
            },
        ]
        _patch_coupling(monkeypatch, over, n_warnings=1, n_errors=0, max_fo=15)

        rule = CouplingMetricRule()
        result = rule.check(_src_dir)

        assert result.text is not None
        assert result.text == "\u2022 utils fo:15/12 \u26a0"

    def test_mixed_severities(
        self, monkeypatch: pytest.MonkeyPatch, _src_dir: Path
    ) -> None:
        """2 warnings + 1 error — each line shows correct severity symbol."""
        over = [
            {
                "module": "pkg.alpha",
                "fan_out": 20,
                "role": "leaf",
                "effective_threshold": 12,
                "severity": "warning",
            },
            {
                "module": "pkg.beta",
                "fan_out": 18,
                "role": "leaf",
                "effective_threshold": 12,
                "severity": "error",
            },
            {
                "module": "pkg.gamma",
                "fan_out": 14,
                "role": "leaf",
                "effective_threshold": 12,
                "severity": "warning",
            },
        ]
        _patch_coupling(monkeypatch, over, n_warnings=2, n_errors=1)

        rule = CouplingMetricRule()
        result = rule.check(_src_dir)

        assert result.text is not None
        lines = result.text.split("\n")
        assert lines[0] == "\u2022 alpha fo:20/12 \u26a0"
        assert lines[1] == "\u2022 beta fo:18/12 \u2718"
        assert lines[2] == "\u2022 gamma fo:14/12 \u26a0"


def test_coupling_text_format_from_root(_patch_coupling_from_root: Any) -> None:
    """text= lines match '\u2022 {leaf} fo:{N}/{T} {\u26a0|\u2718}' pattern."""
    over = [
        _make_over_entry_from_root(
            "axm_audit.core.rules.architecture", 18, 12, "warning"
        ),
        _make_over_entry_from_root("axm_audit.core.engine", 16, 12, "warning"),
        _make_over_entry_from_root("axm_audit.formatters", 14, 10, "error"),
    ]
    result = _patch_coupling_from_root(over, n_warnings=2, n_errors=1, severity="error")

    assert result.text is not None
    lines = result.text.split("\n")
    assert len(lines) == 3
    assert lines[0] == "\u2022 architecture fo:18/12 \u26a0"
    assert lines[1] == "\u2022 engine fo:16/12 \u26a0"
    assert lines[2] == "\u2022 formatters fo:14/10 \u2718"


def test_coupling_text_none_when_passed_from_root(
    _patch_coupling_from_root: Any,
) -> None:
    """text=None when passed=True with 0 violations."""
    result = _patch_coupling_from_root(
        over=[], n_warnings=0, n_errors=0, severity="info"
    )

    assert result.text is None
    assert result.passed is True


def test_coupling_text_single_segment_module_from_root(
    _patch_coupling_from_root: Any,
) -> None:
    """Module name without dots — rsplit returns the name as-is."""
    over = [
        _make_over_entry_from_root("utils", 15, 12, "warning"),
    ]
    result = _patch_coupling_from_root(over, n_warnings=1, n_errors=0)

    assert result.text is not None
    assert result.text == "\u2022 utils fo:15/12 \u26a0"


def test_coupling_text_mixed_severities_from_root(
    _patch_coupling_from_root: Any,
) -> None:
    """2 warnings + 1 error — each line shows correct severity symbol."""
    over = [
        _make_over_entry_from_root("pkg.alpha", 20, 12, "warning"),
        _make_over_entry_from_root("pkg.beta", 18, 12, "warning"),
        _make_over_entry_from_root("pkg.gamma", 25, 12, "error"),
    ]
    result = _patch_coupling_from_root(over, n_warnings=2, n_errors=1, severity="error")

    lines = result.text.split("\n")
    assert len(lines) == 3
    # Each line has the correct severity symbol
    warning_lines = [line for line in lines if line.endswith("\u26a0")]
    error_lines = [line for line in lines if line.endswith("\u2718")]
    assert len(warning_lines) == 2
    assert len(error_lines) == 1
    assert "\u2022 gamma fo:25/12 \u2718" in lines
