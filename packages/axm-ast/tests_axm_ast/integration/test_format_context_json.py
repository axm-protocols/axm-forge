"""Split from ``test_build_context__format_context_json.py``.

Covers ``format_context_json`` integration (depth modes, structural fields).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.context import (
    ContextResult,
    build_context,
    format_context_json,
)

# ─── Helpers ──────────────────────────────────────────────────────────


def _make_pyproject(path: Path, deps: list[str], *, build: str = "hatchling") -> None:
    """Write a minimal pyproject.toml."""
    dep_lines = ", ".join(f'"{d}"' for d in deps)
    (path / "pyproject.toml").write_text(
        f"[project]\n"
        f'name = "testpkg"\n'
        f"dependencies = [{dep_lines}]\n"
        f"[build-system]\n"
        f'requires = ["{build}"]\n'
        f'build-backend = "{build}.build"\n'
    )


def _make_pkg(path: Path, *, modules: dict[str, str] | None = None) -> Path:
    """Create a minimal Python package."""
    pkg = path / "testpkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text('"""Test package."""\n')
    if modules:
        for name, content in modules.items():
            (pkg / name).write_text(content)
    return pkg


@pytest.mark.integration
class TestDepthModeFormatJson:
    """Tests for context depth parameter (format_context_json only)."""

    def _ctx(
        self, tmp_path: Path, *, modules: dict[str, str] | None = None
    ) -> ContextResult:
        """Build a context from a temp package."""
        m = modules or {
            "core.py": (
                '"""Core module."""\n'
                "def greet() -> str:\n"
                '    """Greet."""\n'
                '    return "hi"\n'
                "class Foo:\n"
                '    """Foo class."""\n'
                "    pass\n"
            ),
            "utils.py": (
                '"""Utility helpers."""\n'
                "def helper() -> None:\n"
                '    """Help."""\n'
                "    pass\n"
            ),
        }
        pkg = _make_pkg(tmp_path, modules=m)
        _make_pyproject(tmp_path, ["cyclopts>=3.0"])
        return build_context(pkg, project_root=tmp_path)

    # --- Unit: depth=0 (top-5 modules) ---

    def test_depth0_has_expected_keys(self, tmp_path: Path) -> None:
        """depth=0 has name, python, stack, patterns, top_modules."""
        ctx = self._ctx(tmp_path)
        data = format_context_json(ctx, depth=0)
        assert "name" in data
        assert "python" in data
        assert "stack" in data
        assert "patterns" in data
        assert "top_modules" in data

    def test_depth0_no_full_modules(self, tmp_path: Path) -> None:
        """depth=0 strips full modules and dependency_graph."""
        ctx = self._ctx(tmp_path)
        data = format_context_json(ctx, depth=0)
        assert "modules" not in data
        assert "dependency_graph" not in data
        assert "axm_tools" not in data

    def test_depth0_top_modules_count(self, tmp_path: Path) -> None:
        """top_modules has ≤ 5 entries."""
        ctx = self._ctx(tmp_path)
        data = format_context_json(ctx, depth=0)
        assert len(data["top_modules"]) <= 5

    def test_depth0_top_modules_fields(self, tmp_path: Path) -> None:
        """Each entry has name, symbol_count, stars."""
        ctx = self._ctx(tmp_path)
        data = format_context_json(ctx, depth=0)
        for entry in data["top_modules"]:
            assert "name" in entry
            assert "symbol_count" in entry
            assert "stars" in entry

    def test_depth0_patterns_compact(self, tmp_path: Path) -> None:
        """Compact patterns has only counts + layout."""
        ctx = self._ctx(tmp_path)
        data = format_context_json(ctx, depth=0)
        p = data["patterns"]
        assert "module_count" in p
        assert "function_count" in p
        assert "class_count" in p
        assert "layout" in p

    def test_depth_none_full_context(self, tmp_path: Path) -> None:
        """depth=None returns full context (regression)."""
        ctx = self._ctx(tmp_path)
        data = format_context_json(ctx)
        assert "modules" in data
        assert "dependency_graph" in data
        assert "axm_tools" in data

    # --- depth=1 (sub-packages) ---

    def test_depth1_has_packages(self, tmp_path: Path) -> None:
        """depth=1 returns packages dict."""
        ctx = self._ctx(tmp_path)
        data = format_context_json(ctx, depth=1)
        assert "packages" in data
        assert "top_modules" not in data

    def test_depth1_package_has_counts(self, tmp_path: Path) -> None:
        """Each package entry has modules and symbols counts."""
        ctx = self._ctx(tmp_path)
        data = format_context_json(ctx, depth=1)
        for info in data["packages"].values():
            assert "modules" in info
            assert "symbols" in info
