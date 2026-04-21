"""Integration tests for context module with filesystem."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from axm_ast.core.context import (
    build_context,
    detect_patterns,
    format_context_json,
)

# ─── Helpers ─────────────────────────────────────────────────────────────────


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
class TestDetectPatterns:
    """Test project pattern detection."""

    def test_detect_patterns_all_exports(self, tmp_path: Path) -> None:
        """Counts modules with __all__."""
        pkg = _make_pkg(
            tmp_path,
            modules={
                "core.py": (
                    '"""Core."""\n'
                    '__all__ = ["foo"]\n'
                    "def foo() -> None:\n"
                    '    """Foo."""\n'
                    "    pass\n"
                ),
            },
        )
        from axm_ast.core.analyzer import analyze_package

        info = analyze_package(pkg)
        patterns = detect_patterns(info, tmp_path)
        assert patterns["all_exports_count"] == 1

    def test_detect_patterns_src_layout(self, tmp_path: Path) -> None:
        """Detects src/ layout."""
        src_dir = tmp_path / "src" / "mypkg"
        src_dir.mkdir(parents=True)
        (src_dir / "__init__.py").write_text('"""Pkg."""\n')
        from axm_ast.core.analyzer import analyze_package

        info = analyze_package(src_dir)
        patterns = detect_patterns(info, tmp_path)
        assert patterns["layout"] == "src"

    def test_detect_patterns_flat_layout(self, tmp_path: Path) -> None:
        """Detects flat layout."""
        pkg = _make_pkg(tmp_path)
        from axm_ast.core.analyzer import analyze_package

        info = analyze_package(pkg)
        patterns = detect_patterns(info, tmp_path)
        assert patterns["layout"] == "flat"

    def test_detect_patterns_test_naming(self, tmp_path: Path) -> None:
        """Detects test file naming convention."""
        pkg = _make_pkg(tmp_path)
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_core.py").write_text('"""Test."""\n')
        (tests_dir / "test_utils.py").write_text('"""Test."""\n')
        from axm_ast.core.analyzer import analyze_package

        info = analyze_package(pkg)
        patterns = detect_patterns(info, tmp_path)
        assert patterns["test_count"] == 2


@pytest.mark.integration
class TestBuildContext:
    """Test context orchestrator."""

    def test_build_context_module_list(self, tmp_path: Path) -> None:
        """Context includes module names."""
        core_src = '"""Core."""\ndef f() -> None:\n    """F."""\n    pass\n'
        pkg = _make_pkg(
            tmp_path,
            modules={"core.py": core_src},
        )
        _make_pyproject(tmp_path, [])
        ctx = build_context(pkg, project_root=tmp_path)
        mod_names = [m["name"] for m in ctx["modules"]]
        assert any("core" in n for n in mod_names)


@pytest.mark.integration
class TestContextEdgeCases:
    """Edge cases for context command."""

    def test_empty_package(self, tmp_path: Path) -> None:
        """Minimal package with only __init__.py."""
        pkg = _make_pkg(tmp_path)
        _make_pyproject(tmp_path, [])
        ctx = build_context(pkg, project_root=tmp_path)
        assert ctx["name"] == "testpkg"
        assert len(ctx["modules"]) >= 1

    def test_no_pyproject(self, tmp_path: Path) -> None:
        """No pyproject.toml still produces context from AST."""
        pkg = _make_pkg(tmp_path)
        ctx = build_context(pkg, project_root=tmp_path)
        assert ctx["stack"] == {}
        assert len(ctx["modules"]) >= 1

    def test_poetry_project(self, tmp_path: Path) -> None:
        """Poetry-based project detected."""
        pkg = _make_pkg(tmp_path)
        _make_pyproject(tmp_path, ["click>=8.0"], build="poetry.core.masonry.api")
        ctx = build_context(pkg, project_root=tmp_path)
        assert "packaging" in ctx["stack"]

    def test_namespace_package(self, tmp_path: Path) -> None:
        """Package without __init__.py (namespace pkg)."""
        pkg = tmp_path / "nspkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text(
            '"""Module."""\ndef hello() -> None:\n    """Hello."""\n    pass\n'
        )
        from axm_ast.core.analyzer import analyze_package

        analyze_package(pkg)
        ctx = build_context(pkg, project_root=tmp_path)
        assert "name" in ctx
        assert len(ctx["modules"]) >= 1


@pytest.mark.integration
class TestDepthMode:
    """Tests for context depth parameter."""

    def _ctx(
        self, tmp_path: Path, *, modules: dict[str, str] | None = None
    ) -> dict[str, Any]:
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

    # --- Edge cases ---

    def test_empty_package_depth0(self, tmp_path: Path) -> None:
        """Empty package with only __init__.py has exactly 1 top module."""
        pkg = _make_pkg(tmp_path)
        _make_pyproject(tmp_path, [])
        ctx = build_context(pkg, project_root=tmp_path)
        data = format_context_json(ctx, depth=0)
        assert len(data["top_modules"]) == 1

    # --- python field defaults ---

    def test_python_none_when_not_declared(self, tmp_path: Path) -> None:
        """python is None when project has no requires-python."""
        pkg = _make_pkg(tmp_path)
        _make_pyproject(tmp_path, ["cyclopts>=3.0"])
        ctx = build_context(pkg, project_root=tmp_path)
        data = format_context_json(ctx, depth=0)
        assert data["python"] is None

    def test_python_preserved_when_declared(self, tmp_path: Path) -> None:
        """python reflects declared requires-python value."""
        pkg = _make_pkg(tmp_path)
        _make_pyproject(tmp_path, ["cyclopts>=3.0"])
        # Add requires-python to pyproject.toml
        pyproject = tmp_path / "pyproject.toml"
        content = pyproject.read_text()
        content = content.replace("[project]", '[project]\nrequires-python = ">=3.12"')
        pyproject.write_text(content)
        ctx = build_context(pkg, project_root=tmp_path)
        data = format_context_json(ctx, depth=0)
        assert data["python"] == ">=3.12"

    def test_python_none_consistency_across_depths(self, tmp_path: Path) -> None:
        """python is None at all depth levels when not declared."""
        pkg = _make_pkg(tmp_path)
        _make_pyproject(tmp_path, [])
        ctx = build_context(pkg, project_root=tmp_path)
        for d in (0, 1, 2):
            data = format_context_json(ctx, depth=d)
            assert data["python"] is None, f"depth={d} returned {data['python']!r}"

    # --- Dogfood ---


# ─── Format + dogfood ──────────────────────────────────────────────────────

FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.mark.integration
def test_context_text_contains_sections(tmp_path: Path) -> None:
    """Text output has key sections."""
    pkg = _make_pkg(tmp_path)
    _make_pyproject(tmp_path, ["cyclopts>=3.0", "pydantic>=2.0"])
    ctx = build_context(pkg, project_root=tmp_path)
    from axm_ast.core.context import format_context

    text = format_context(ctx)
    assert "testpkg" in text
    assert "Stack" in text or "stack" in text.lower()
    assert "cyclopts" in text


@pytest.mark.integration
def test_context_real_package() -> None:
    """Dogfood: run on axm-ast itself."""
    ast_root = FIXTURES.parent / "src" / "axm_ast"
    project_root = FIXTURES.parent
    if not ast_root.exists():
        pytest.skip("axm-ast source not found at expected path")
    ctx = build_context(ast_root, project_root=project_root)
    assert ctx["name"] == "axm_ast"
    assert len(ctx["modules"]) >= 1
    assert "cli" in ctx["stack"] or "cyclopts" in str(ctx["stack"])
