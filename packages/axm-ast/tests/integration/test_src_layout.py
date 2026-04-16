"""Integration tests for src-layout edge detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.analyzer import analyze_package


@pytest.mark.integration
def test_build_edges_src_layout(tmp_path: Path) -> None:
    """analyze_package returns non-empty dependency_edges for a src-layout package."""
    pkg_dir = tmp_path / "src" / "mypkg"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "core.py").write_text("from mypkg import models\n")
    (pkg_dir / "models.py").write_text("from mypkg import core\n")

    pkg = analyze_package(tmp_path)
    assert len(pkg.dependency_edges) > 0, (
        "Expected non-empty edges for src-layout package"
    )
