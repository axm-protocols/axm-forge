"""Tests for core/templates.py — API + scaffold template output (AXM-75 AC)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from axm_init.core.templates import TemplateInfo
from axm_init.models.results import ScaffoldResult
from tests.integration._helpers import _build_scaffold_tree


class TestTemplateInfo:
    """TemplateInfo model is still usable."""

    def test_template_info_creation(self, tmp_path: Path) -> None:
        """TemplateInfo can be instantiated."""
        info = TemplateInfo(
            name="python",
            description="A python project",
            path=tmp_path,
        )
        assert info.name == "python"
        assert info.path == tmp_path


@pytest.fixture()
def _mock_scaffold(tmp_path: Path) -> Iterator[tuple[Path, MagicMock]]:
    """Patch CopierAdapter.copy() and scaffold a fake tree.

    Returns (project_dir, mock_adapter_instance).
    """
    files = _build_scaffold_tree(tmp_path, "clean-init-test")

    mock_result = ScaffoldResult(
        success=True,
        path=str(tmp_path),
        message="Project scaffolded via Copier",
        files_created=files,
    )

    with patch("axm_init.cli.CopierAdapter") as mock_cls:
        mock_cls.return_value.copy.return_value = mock_result
        yield tmp_path, mock_cls.return_value


# ── AC2: No hello() in __init__.py ──────────────────────────────────────────


class TestScaffoldNoHello:
    """AC2: __init__.py template uses version import pattern (no hello())."""

    def test_scaffold_no_hello(self, tmp_path: Path) -> None:
        """Scaffolded __init__.py must not contain hello()."""
        _build_scaffold_tree(tmp_path, "clean-init-test")

        init_files = list(tmp_path.rglob("__init__.py"))
        pkg_init = [
            f for f in init_files if "src" in str(f) and f.parent.name != "core"
        ]
        assert len(pkg_init) >= 1, f"Expected package __init__.py, found: {init_files}"

        content = pkg_init[0].read_text()
        assert "def hello" not in content, (
            f"hello() function should not be in __init__.py: {content}"
        )

    def test_scaffold_version_import(self, tmp_path: Path) -> None:
        """__init__.py contains version import with try/except."""
        _build_scaffold_tree(tmp_path, "ver-import-test")

        init_files = list(tmp_path.rglob("__init__.py"))
        pkg_init = [
            f for f in init_files if "src" in str(f) and f.parent.name != "core"
        ]
        assert len(pkg_init) >= 1

        content = pkg_init[0].read_text()
        assert "__version__" in content
        assert "try" in content, "Should use try/except for version import"


# ── AC3: No utils/ directory ────────────────────────────────────────────────


class TestScaffoldNoUtilsDir:
    """AC3: No utils/ directory created by default."""

    def test_scaffold_no_utils_dir(self, tmp_path: Path) -> None:
        """Scaffolded project must not have a utils/ directory in src/."""
        _build_scaffold_tree(tmp_path, "no-utils-test", utils=False)

        src_dirs = list(tmp_path.rglob("src"))
        if src_dirs:
            utils_dirs = list(src_dirs[0].rglob("utils"))
            assert len(utils_dirs) == 0, (
                f"utils/ should not exist in src/: {utils_dirs}"
            )


# ── AC4: Doc templates have no hello() reference ────────────────────────────


class TestScaffoldDocsNoHello:
    """AC4: Doc templates use version/MCP example instead of hello()."""

    def test_scaffold_docs_no_hello(self, tmp_path: Path) -> None:
        """README, index.md, getting-started.md have no hello() reference."""
        _build_scaffold_tree(tmp_path, "docs-test")

        # Check README
        readmes = list(tmp_path.rglob("README.md"))
        for readme in readmes:
            content = readme.read_text()
            assert "hello" not in content.lower(), f"hello() in {readme}"

        # Check docs/index.md
        index_files = list(tmp_path.rglob("docs/index.md"))
        for idx in index_files:
            content = idx.read_text()
            assert "hello" not in content.lower(), f"hello() in {idx}"

        # Check docs/tutorials/getting-started.md
        gs_files = list(tmp_path.rglob("getting-started.md"))
        for gs in gs_files:
            content = gs.read_text()
            assert "hello" not in content.lower(), f"hello() in {gs}"
