"""Split from ``test_build_context__format_context_json.py``.

Covers ``build_context`` + ``format_context`` integration (text output).
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
