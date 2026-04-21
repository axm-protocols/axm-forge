"""Integration tests for call-site and reference extraction.

Covers tree-sitter + filesystem.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.callers import (
    find_callers,
    find_callers_workspace,
)
from axm_ast.models.nodes import WorkspaceInfo

pytestmark = pytest.mark.integration


class TestFindCallers:
    """Test cross-module caller search."""

    def test_finds_direct_call(self, tmp_path: Path) -> None:
        """Finds a direct function call in another module."""
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Pkg."""\ndef greet() -> str:\n    """Greet."""\n    return "hi"\n'
        )
        (pkg_dir / "cli.py").write_text(
            '"""CLI."""\ndef main() -> None:\n    """Main."""\n    greet()\n'
        )
        pkg = analyze_package(pkg_dir)
        results = find_callers(pkg, "greet")
        assert len(results) == 1
        assert results[0].symbol == "greet"

    def test_no_callers(self, tmp_path: Path) -> None:
        """Symbol never called returns empty list."""
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Pkg."""\ndef lonely() -> None:\n    """Lonely."""\n    pass\n'
        )
        pkg = analyze_package(pkg_dir)
        results = find_callers(pkg, "lonely")
        assert results == []

    def test_multiple_callers(self, tmp_path: Path) -> None:
        """Same symbol called from multiple places."""
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text('"""Pkg."""\n')
        (pkg_dir / "a.py").write_text(
            '"""A."""\ndef use_it() -> None:\n    """Use."""\n    helper()\n'
        )
        (pkg_dir / "b.py").write_text(
            '"""B."""\ndef also_use() -> None:\n    """Also."""\n    helper()\n'
        )
        pkg = analyze_package(pkg_dir)
        results = find_callers(pkg, "helper")
        assert len(results) == 2


class TestFindCallersWorkspace:
    """Test cross-package caller search."""

    def test_finds_caller_across_packages(self, tmp_path: Path) -> None:
        """Symbol called in pkg_b is found with pkg_a:: prefix."""
        pkg_a = tmp_path / "pkg_a"
        pkg_a.mkdir()
        (pkg_a / "__init__.py").write_text(
            '"""Pkg A."""\ndef shared() -> None:\n    """Shared."""\n    pass\n'
        )

        pkg_b = tmp_path / "pkg_b"
        pkg_b.mkdir()
        (pkg_b / "__init__.py").write_text('"""Pkg B."""\n')
        (pkg_b / "use.py").write_text(
            '"""Use."""\ndef main() -> None:\n    """Main."""\n    shared()\n'
        )

        ws = WorkspaceInfo(
            name="test-ws",
            root=tmp_path,
            packages=[
                analyze_package(pkg_a),
                analyze_package(pkg_b),
            ],
        )
        results = find_callers_workspace(ws, "shared")
        assert len(results) == 1
        assert "::" in results[0].module
        assert results[0].symbol == "shared"
