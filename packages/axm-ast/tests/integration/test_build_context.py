"""Split from ``test_build_context__format_context_json.py``.

Covers ``build_context`` integration.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.context import build_context

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


def test_empty_package(tmp_path: Path) -> None:
    """Minimal package with only __init__.py."""
    pkg = _make_pkg(tmp_path)
    _make_pyproject(tmp_path, [])
    ctx = build_context(pkg, project_root=tmp_path)
    assert ctx["name"] == "testpkg"
    assert len(ctx["modules"]) >= 1


def test_no_pyproject(tmp_path: Path) -> None:
    """No pyproject.toml still produces context from AST."""
    pkg = _make_pkg(tmp_path)
    ctx = build_context(pkg, project_root=tmp_path)
    assert ctx["stack"] == {}
    assert len(ctx["modules"]) >= 1


def test_poetry_project(tmp_path: Path) -> None:
    """Poetry-based project detected."""
    pkg = _make_pkg(tmp_path)
    _make_pyproject(tmp_path, ["click>=8.0"], build="poetry.core.masonry.api")
    ctx = build_context(pkg, project_root=tmp_path)
    assert "packaging" in ctx["stack"]


@pytest.mark.integration
def test_context_real_package() -> None:
    """Dogfood: run on axm-ast itself."""
    package_root = Path(__file__).resolve().parents[2]
    ast_root = package_root / "src" / "axm_ast"
    project_root = package_root
    if not ast_root.exists():
        pytest.skip("axm-ast source not found at expected path")
    ctx = build_context(ast_root, project_root=project_root)
    assert ctx["name"] == "axm_ast"
    assert len(ctx["modules"]) >= 1
    assert "cli" in ctx["stack"] or "cyclopts" in str(ctx["stack"])
