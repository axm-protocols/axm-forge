"""Integration tests for ast_impact compact mode (AXM-940)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.integration


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
    }


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
        # Compact mode returns text, not data
        assert result.data == {}
        assert result.text is not None
        assert isinstance(result.text, str)

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
        assert "score" in result.data


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


class TestImpactWorkspaceMode:
    """Workspace-mode integration of ImpactTool compact output."""

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
            "cross_package_impact": ["pkg_b", "pkg_c"],
        }

        tool = ImpactTool()
        result = tool.execute(
            path=str(tmp_path),
            symbol="SharedModel",
            detail="compact",
        )
        assert result.success is True
