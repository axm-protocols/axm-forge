"""Split from ``test_build_context__format_context_json.py``.

Covers ``analyze_package`` + ``build_context`` integration.
"""

from __future__ import annotations

from pathlib import Path

from axm_ast.core.context import build_context


def test_namespace_package(tmp_path: Path) -> None:
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
