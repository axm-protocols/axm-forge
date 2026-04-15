from __future__ import annotations

import ast
import textwrap
from pathlib import Path

from axm_audit.core.rules.architecture import (
    _extract_imports_with_lines,
    _is_cross_package_deep_import,
    _read_boundary_config,
)

# ---------------------------------------------------------------------------
# _is_cross_package_deep_import
# ---------------------------------------------------------------------------


class TestIsCrossPackageDeepImportTrue:
    """Import targeting a sub-module of a *different* internal package."""

    def test_cross_package_deep_import(self) -> None:
        assert (
            _is_cross_package_deep_import(
                "axm_ticket.utils",
                ["axm_engine", "axm_ticket"],
                current_package="axm_engine",
            )
            is True
        )


class TestIsCrossPackageDeepImportFalseRoot:
    """Root-level import of another package is NOT deep."""

    def test_root_level_import(self) -> None:
        assert (
            _is_cross_package_deep_import(
                "axm_ticket",
                ["axm_engine", "axm_ticket"],
                current_package="axm_engine",
            )
            is False
        )


class TestIsCrossPackageDeepImportFalseSamePkg:
    """Deep import within the *same* package is not cross-package."""

    def test_same_package_deep_import(self) -> None:
        assert (
            _is_cross_package_deep_import(
                "axm_engine.core",
                ["axm_engine", "axm_ticket"],
                current_package="axm_engine",
            )
            is False
        )


class TestIsCrossPackageDeepImportFalseExternal:
    """External library deep import is not flagged."""

    def test_external_deep_import(self) -> None:
        assert (
            _is_cross_package_deep_import(
                "httpx.client",
                ["axm_engine"],
                current_package="axm_engine",
            )
            is False
        )


# ---------------------------------------------------------------------------
# _extract_imports_with_lines
# ---------------------------------------------------------------------------


class TestExtractImportsWithLines:
    """Returns (module, line_number) tuples for top-level imports."""

    def test_three_imports(self) -> None:
        source = textwrap.dedent("""\
            import foo
            x = 1
            from bar import thing
            y = 2
            import baz
        """)
        tree = ast.parse(source)
        result = _extract_imports_with_lines(tree)
        assert result == [("foo", 1), ("bar", 3), ("baz", 5)]


# ---------------------------------------------------------------------------
# _read_boundary_config
# ---------------------------------------------------------------------------


class TestReadBoundaryConfigEmpty:
    """No import-boundary section → empty allow list."""

    def test_empty_config(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.axm-audit]\n")
        result = _read_boundary_config(tmp_path)
        assert result == []


class TestReadBoundaryConfigWithAllows:
    """Parses allow list from pyproject.toml."""

    def test_with_allows(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[tool.axm-audit.import-boundary]\nallow = ["axm_engine.hooks"]\n'
        )
        result = _read_boundary_config(tmp_path)
        assert result == ["axm_engine.hooks"]
