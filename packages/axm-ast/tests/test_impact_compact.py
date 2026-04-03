"""TDD tests for compact output mode on ast_impact (AXM-940).

Tests cover:
- Unit: format_impact_compact formatter
- Functional: ImpactTool.execute(detail="compact"), ImpactHook with detail param
- Edge cases: not found, no tests, workspace mode
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_impact_dict(
    symbol: str = "greet",
    *,
    callers: list[dict[str, Any]] | None = None,
    test_files: list[str] | None = None,
    definition: dict[str, Any] | None = None,
    score: str = "MEDIUM",
) -> dict[str, Any]:
    """Build a realistic impact analysis dict."""
    return {
        "symbol": symbol,
        "definition": definition
        or {"module": "demo.core", "line": 10, "kind": "function"},
        "callers": callers or [],
        "type_refs": [],
        "reexports": [],
        "affected_modules": ["demo.core", "demo.cli"],
        "test_files": test_files or [],
        "git_coupled": [],
        "score": score,
        "severity": score,
    }


# ─── Unit: format_impact_compact ─────────────────────────────────────────────


class TestFormatImpactCompactSingle:
    """Single-symbol compact formatting."""

    def test_format_impact_compact_single(self) -> None:
        """1 definition + 3 callers → table row + caller summary."""
        from axm_ast.tools.impact import format_impact_compact

        impact = _make_impact_dict(
            symbol="greet",
            callers=[
                {"name": "main", "module": "demo.cli", "line": 10},
                {"name": "run", "module": "demo.app", "line": 20},
                {"name": "test_greet", "module": "tests.test_core"},
            ],
        )
        result = format_impact_compact(impact)
        assert isinstance(result, str)
        # Table headers
        assert "Symbol" in result
        assert "Score" in result
        # Symbol row with definition location
        assert "greet" in result
        assert "demo.core:10" in result
        assert "MEDIUM" in result
        # Caller details: prod callers with module:line, test callers grouped
        assert "Prod:" in result
        assert "demo.cli:10" in result
        assert "demo.app:20" in result
        assert "test_core" in result


class TestFormatImpactCompactMulti:
    """Multi-symbol (merged) compact formatting."""

    def test_format_impact_compact_multi(self) -> None:
        """Merged dict with 4 definitions → table with 4 rows, merged callers."""
        from axm_ast.tools.impact import format_impact_compact

        merged: dict[str, Any] = {
            "symbol": "A\nB\nC\nD",
            "definitions": [
                {"module": "mod_a", "line": 1, "kind": "function"},
                {"module": "mod_b", "line": 5, "kind": "function"},
                {"module": "mod_c", "line": 10, "kind": "class"},
                {"module": "mod_d", "line": 20, "kind": "method"},
            ],
            "callers": [
                {"name": "x", "module": "mod_x"},
                {"name": "y", "module": "mod_y"},
            ],
            "type_refs": [],
            "reexports": [],
            "affected_modules": ["mod_a", "mod_b", "mod_c", "mod_d"],
            "test_files": [],
            "git_coupled": [],
            "score": "HIGH",
        }
        result = format_impact_compact(merged)
        assert isinstance(result, str)
        # Should have rows for all definitions
        assert "mod_a" in result
        assert "mod_b" in result
        assert "mod_c" in result
        assert "mod_d" in result
        assert "HIGH" in result


class TestFormatImpactCompactNoCallers:
    """Compact formatting when no callers exist."""

    def test_format_impact_compact_no_callers(self) -> None:
        """Symbol with 0 callers → table shows em-dash for callers."""
        from axm_ast.tools.impact import format_impact_compact

        impact = _make_impact_dict(symbol="lonely", callers=[], score="LOW")
        result = format_impact_compact(impact)
        assert isinstance(result, str)
        assert "\u2014" in result  # em-dash = no callers
        assert "lonely" in result


class TestFormatImpactCompactTestExposure:
    """Compact formatting with test file exposure."""

    def test_format_impact_compact_test_exposure(self) -> None:
        """Dict with test_files → footer lists file names."""
        from axm_ast.tools.impact import format_impact_compact

        impact = _make_impact_dict(
            test_files=["test_core.py", "test_cli.py", "test_integration.py"],
        )
        result = format_impact_compact(impact)
        assert isinstance(result, str)
        assert "test_core.py" in result
        assert "test_cli.py" in result
        assert "test_integration.py" in result


# ─── Functional: ImpactTool with detail="compact" ────────────────────────────


@pytest.fixture
def sample_pkg(tmp_path: Path) -> Path:
    """Create a minimal package for tool-level tests."""
    pkg = tmp_path / "src" / "demo"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(
        '"""Demo."""\n\n__all__ = ["greet"]\n\nfrom demo.core import greet\n'
    )
    (pkg / "core.py").write_text(
        '"""Core."""\n\n'
        '__all__ = ["greet"]\n\n\n'
        "def greet(name: str) -> str:\n"
        '    """Say hello."""\n'
        '    return f"Hello {name}"\n'
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n'
    )
    return tmp_path


class TestImpactToolCompactMode:
    """ImpactTool.execute with detail='compact'."""

    def test_impact_tool_compact_mode(self, sample_pkg: Path) -> None:
        """ImpactTool.execute(detail='compact') on sample_pkg returns compact string."""
        from axm_ast.tools.impact import ImpactTool

        tool = ImpactTool()
        result = tool.execute(
            path=str(sample_pkg / "src" / "demo"),
            symbol="greet",
            detail="compact",
        )
        assert result.success is True
        # Compact mode wraps markdown in {"compact": "..."}
        assert isinstance(result.data, dict)
        assert "compact" in result.data
        assert isinstance(result.data["compact"], str)

    def test_impact_tool_full_unchanged(self, sample_pkg: Path) -> None:
        """ImpactTool.execute() without detail → same JSON output (regression)."""
        from axm_ast.tools.impact import ImpactTool

        tool = ImpactTool()
        result = tool.execute(
            path=str(sample_pkg / "src" / "demo"),
            symbol="greet",
        )
        assert result.success is True
        # Default mode: data is a dict with impact fields
        assert isinstance(result.data, dict)
        assert "severity" in result.data


# ─── Functional: ImpactHook with detail param ────────────────────────────────


class TestImpactHookCompact:
    """ImpactHook with detail='compact'."""

    @patch("axm_ast.core.impact.analyze_impact")
    def test_impact_hook_compact_single(
        self,
        mock_impact: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Single symbol, detail=compact → compact markdown."""
        from axm_ast.hooks.impact import ImpactHook

        mock_impact.return_value = _make_impact_dict(
            symbol="Foo",
            callers=[{"name": "bar", "module": "mod_b"}],
        )

        hook = ImpactHook()
        result = hook.execute(
            {},
            symbol="Foo",
            path=str(tmp_path),
            detail="compact",
        )

        assert result.success
        # Compact mode should produce markdown string in metadata
        impact_data = result.metadata.get("impact")
        assert impact_data is not None
        assert isinstance(impact_data, str)
        assert "Foo" in impact_data

    @patch("axm_ast.core.impact.analyze_impact")
    def test_impact_hook_compact_multi(
        self,
        mock_impact: MagicMock,
        tmp_path: Path,
    ) -> None:
        """ImpactHook with 3 symbols, detail=compact → merged compact table."""
        from axm_ast.hooks.impact import ImpactHook

        def side_effect(_path: Path, sym: str, **_kw: object) -> dict[str, Any]:
            return _make_impact_dict(
                symbol=sym,
                callers=[{"name": f"caller_{sym}", "module": f"mod_{sym}"}],
            )

        mock_impact.side_effect = side_effect

        hook = ImpactHook()
        result = hook.execute(
            {},
            symbol="A\nB\nC",
            path=str(tmp_path),
            detail="compact",
        )

        assert result.success
        impact_data = result.metadata.get("impact")
        assert isinstance(impact_data, str)
        # All three symbols should appear in the merged compact output
        assert "A" in impact_data
        assert "B" in impact_data
        assert "C" in impact_data


# ─── Edge cases ──────────────────────────────────────────────────────────────


class TestImpactCompactEdgeCases:
    """Edge cases for compact output mode."""

    def test_symbol_not_found(self) -> None:
        """Unknown symbol → row with 'not found' indicator."""
        from axm_ast.tools.impact import format_impact_compact

        impact: dict[str, Any] = {
            "symbol": "missing_func",
            "definition": None,
            "callers": [],
            "type_refs": [],
            "reexports": [],
            "affected_modules": [],
            "test_files": [],
            "git_coupled": [],
            "score": "LOW",
            "severity": "LOW",
            "error": "Symbol 'missing_func' not found",
        }
        result = format_impact_compact(impact)
        assert isinstance(result, str)
        assert "not found" in result.lower() or "missing_func" in result

    def test_no_test_files(self) -> None:
        """Symbol with no tests → footer says 'no test coverage'."""
        from axm_ast.tools.impact import format_impact_compact

        impact = _make_impact_dict(test_files=[])
        result = format_impact_compact(impact)
        assert isinstance(result, str)
        assert "no test coverage" in result

    @patch("axm_ast.tools.impact.ImpactTool._analyze_single")
    def test_workspace_mode(self, mock_analyze: MagicMock, tmp_path: Path) -> None:
        """Workspace path with cross-package impact → all packages in table."""
        from axm_ast.tools.impact import ImpactTool

        mock_analyze.return_value = {
            "symbol": "SharedModel",
            "definition": {"module": "pkg_a.models", "line": 5, "kind": "class"},
            "callers": [
                {"name": "use_model", "module": "pkg_b.service"},
                {"name": "test_model", "module": "pkg_c.tests"},
            ],
            "type_refs": [],
            "reexports": [],
            "affected_modules": ["pkg_a.models", "pkg_b.service", "pkg_c.tests"],
            "test_files": [],
            "git_coupled": [],
            "score": "HIGH",
            "severity": "HIGH",
            "cross_package_impact": ["pkg_b", "pkg_c"],
        }

        tool = ImpactTool()
        result = tool.execute(
            path=str(tmp_path),
            symbol="SharedModel",
            detail="compact",
        )
        assert result.success is True
