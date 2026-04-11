"""TDD tests for axm-ast context — one-shot project dump."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from axm_ast.core.context import (
    build_context,
    detect_axm_tools,
    detect_patterns,
    detect_stack,
    format_context,
    format_context_json,
)

# ─── Helpers ─────────────────────────────────────────────────────────────────

FIXTURES = Path(__file__).parent / "fixtures"


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


# ─── Unit: detect_stack ──────────────────────────────────────────────────────


class TestDetectStack:
    """Test pyproject.toml dependency categorization."""

    def test_detect_stack_cyclopts(self, tmp_path: Path) -> None:
        """Detects cyclopts as CLI framework."""
        _make_pyproject(tmp_path, ["cyclopts>=3.0"])
        stack = detect_stack(tmp_path)
        assert "cli" in stack
        assert "cyclopts" in stack["cli"]

    def test_detect_stack_pydantic(self, tmp_path: Path) -> None:
        """Detects pydantic as models framework."""
        _make_pyproject(tmp_path, ["pydantic>=2.0"])
        stack = detect_stack(tmp_path)
        assert "models" in stack
        assert "pydantic" in stack["models"]

    def test_detect_stack_multiple(self, tmp_path: Path) -> None:
        """Categorizes all deps correctly."""
        _make_pyproject(
            tmp_path,
            ["cyclopts>=3.0", "pydantic>=2.0", "tree-sitter>=0.24"],
        )
        stack = detect_stack(tmp_path)
        assert "cli" in stack
        assert "models" in stack

    def test_detect_stack_no_pyproject(self, tmp_path: Path) -> None:
        """No pyproject.toml → empty stack."""
        stack = detect_stack(tmp_path)
        assert stack == {}

    def test_detect_stack_unknown_deps(self, tmp_path: Path) -> None:
        """Unknown deps are not categorized."""
        _make_pyproject(tmp_path, ["obscure-lib>=1.0"])
        stack = detect_stack(tmp_path)
        # obscure-lib shouldn't appear in any category
        all_deps = [d for deps in stack.values() for d in deps]
        assert "obscure-lib" not in all_deps

    def test_detect_stack_dev_deps(self, tmp_path: Path) -> None:
        """Detects dev dependencies (pytest, ruff, mypy)."""
        _make_pyproject(tmp_path, [])
        pyproject = tmp_path / "pyproject.toml"
        content = pyproject.read_text()
        content += (
            '\n[dependency-groups]\ndev = ["pytest>=8.0", "ruff>=0.8", "mypy>=1.14"]\n'
        )
        pyproject.write_text(content)
        stack = detect_stack(tmp_path)
        assert "tests" in stack
        assert "lint" in stack
        assert "types" in stack

    def test_detect_stack_build_system(self, tmp_path: Path) -> None:
        """Detects build system from [build-system]."""
        _make_pyproject(tmp_path, [], build="hatchling")
        stack = detect_stack(tmp_path)
        assert "packaging" in stack
        assert "hatchling" in stack["packaging"]

    def test_detect_stack_poetry(self, tmp_path: Path) -> None:
        """Detects poetry from build-system."""
        _make_pyproject(tmp_path, [], build="poetry.core.masonry.api")
        stack = detect_stack(tmp_path)
        assert "packaging" in stack


# ─── Unit: detect_axm_tools ──────────────────────────────────────────────────


class TestDetectAxmTools:
    """Test AXM ecosystem tool detection."""

    def test_detect_axm_tools_available(self) -> None:
        """Finds installed AXM tools."""
        with patch("shutil.which", return_value="/usr/bin/axm-ast"):
            tools = detect_axm_tools()
        assert "axm-ast" in tools

    def test_detect_axm_tools_missing(self) -> None:
        """Missing tools are not included."""
        with patch("shutil.which", return_value=None):
            tools = detect_axm_tools()
        assert tools == {}

    def test_detect_axm_tools_partial(self) -> None:
        """Only installed tools are returned."""

        def _mock_which(name: str) -> str | None:
            return "/usr/bin/" + name if name == "axm-ast" else None

        with patch("shutil.which", side_effect=_mock_which):
            tools = detect_axm_tools()
        assert "axm-ast" in tools
        assert "axm-audit" not in tools


# ─── Unit: detect_patterns ───────────────────────────────────────────────────


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
        assert patterns["all_exports_count"] >= 1

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


# ─── Unit: build_context ─────────────────────────────────────────────────────


class TestBuildContext:
    """Test context orchestrator."""

    def test_build_context_returns_dict(self, tmp_path: Path) -> None:
        """build_context returns a structured dict."""
        pkg = _make_pkg(tmp_path)
        _make_pyproject(tmp_path, ["cyclopts>=3.0"])
        ctx = build_context(pkg, project_root=tmp_path)
        assert isinstance(ctx, dict)
        assert "name" in ctx
        assert "stack" in ctx
        assert "patterns" in ctx
        assert "modules" in ctx

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


# ─── Edge cases ──────────────────────────────────────────────────────────────


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
        # Should not crash
        from axm_ast.core.analyzer import analyze_package

        analyze_package(pkg)
        ctx = build_context(pkg, project_root=tmp_path)
        assert isinstance(ctx, dict)


# ─── Functional: format + CLI ────────────────────────────────────────────────


class TestContextFunctional:
    """Functional tests for context output."""

    def test_context_text_contains_sections(self, tmp_path: Path) -> None:
        """Text output has key sections."""
        pkg = _make_pkg(tmp_path)
        _make_pyproject(tmp_path, ["cyclopts>=3.0", "pydantic>=2.0"])
        ctx = build_context(pkg, project_root=tmp_path)
        text = format_context(ctx)
        assert "testpkg" in text
        assert "Stack" in text or "stack" in text.lower()
        assert "cyclopts" in text

    def test_context_json_valid(self, tmp_path: Path) -> None:
        """JSON output contains all expected keys."""
        pkg = _make_pkg(tmp_path)
        _make_pyproject(tmp_path, ["pydantic>=2.0"])
        ctx = build_context(pkg, project_root=tmp_path)
        data = format_context_json(ctx)
        assert isinstance(data, dict)
        assert "name" in data
        assert "stack" in data
        assert "modules" in data
        assert "axm_tools" in data

    def test_context_real_package(self) -> None:
        """Dogfood: run on axm-ast itself."""
        ast_root = FIXTURES.parent.parent / "src" / "axm_ast"
        project_root = FIXTURES.parent.parent
        if ast_root.exists():
            ctx = build_context(ast_root, project_root=project_root)
            assert ctx["name"] == "axm_ast"
            assert len(ctx["modules"]) > 5
            assert "cli" in ctx["stack"] or "cyclopts" in str(ctx["stack"])

    def test_context_cli_text(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """CLI context command produces output."""
        from axm_ast.cli import app

        pkg = _make_pkg(tmp_path)
        _make_pyproject(tmp_path, ["cyclopts>=3.0"])
        with pytest.raises(SystemExit):
            app(["context", str(pkg)])
        captured = capsys.readouterr()
        assert "testpkg" in captured.out

    def test_context_cli_json(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """CLI --json produces valid JSON."""
        import json

        from axm_ast.cli import app

        pkg = _make_pkg(tmp_path)
        _make_pyproject(tmp_path, ["pydantic>=2.0"])
        with pytest.raises(SystemExit):
            app(["context", str(pkg), "--json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, dict)


# ─── Depth mode ──────────────────────────────────────────────────────────────


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

    def test_small_package_depth0(self, tmp_path: Path) -> None:
        """Package with < 5 modules: top_modules has actual count."""
        ctx = self._ctx(tmp_path)
        data = format_context_json(ctx, depth=0)
        assert len(data["top_modules"]) <= len(ctx["modules"])

    def test_empty_package_depth0(self, tmp_path: Path) -> None:
        """Empty package: top_modules is empty or 1 entry."""
        pkg = _make_pkg(tmp_path)
        _make_pyproject(tmp_path, [])
        ctx = build_context(pkg, project_root=tmp_path)
        data = format_context_json(ctx, depth=0)
        assert len(data["top_modules"]) <= 1

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
        # Inject python version into built context
        ctx = build_context(pkg, project_root=tmp_path)
        ctx["python"] = "3.12"
        data = format_context_json(ctx, depth=0)
        assert data["python"] == "3.12"

    def test_python_none_consistency_across_depths(self, tmp_path: Path) -> None:
        """python is None at all depth levels when not declared."""
        pkg = _make_pkg(tmp_path)
        _make_pyproject(tmp_path, [])
        ctx = build_context(pkg, project_root=tmp_path)
        for d in (0, 1, 2):
            data = format_context_json(ctx, depth=d)
            assert data["python"] is None, f"depth={d} returned {data['python']!r}"

    def test_python_depth_none_passthrough(self, tmp_path: Path) -> None:
        """depth=None returns full context; python passes through as-is."""
        pkg = _make_pkg(tmp_path)
        _make_pyproject(tmp_path, [])
        ctx = build_context(pkg, project_root=tmp_path)
        data = format_context_json(ctx)  # depth=None
        assert data["python"] == ctx["python"]

    # --- Dogfood ---

    def test_depth0_size_under_1k(self) -> None:
        """depth=0 output < 1024 bytes on axm-ast itself."""
        import json

        ast_root = FIXTURES.parent.parent / "src" / "axm_ast"
        project_root = FIXTURES.parent.parent
        if ast_root.exists():
            ctx = build_context(ast_root, project_root=project_root)
            data = format_context_json(ctx, depth=0)
            raw = json.dumps(data)
            assert len(raw) < 1024, f"depth=0 output too large: {len(raw)} bytes"
