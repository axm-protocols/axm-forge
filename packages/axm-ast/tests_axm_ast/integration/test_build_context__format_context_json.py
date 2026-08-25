"""Split from original mixed file.

Covers ``build_context`` + ``format_context_json`` integration (depth modes
that exercise both build and format together).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.context import build_context, format_context_json

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
class TestDepthModeBuildContextJson:
    """Tests exercising build_context + format_context_json together."""

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
