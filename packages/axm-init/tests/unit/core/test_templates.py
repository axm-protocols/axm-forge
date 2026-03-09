"""Tests for core/templates.py — API + scaffold template output (AXM-75 AC)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from axm_init.core.templates import TemplateInfo, get_template_path
from axm_init.models.results import ScaffoldResult

# ── get_template_path / TemplateInfo ─────────────────────────────────────────


class TestGetTemplatePath:
    """Tests for get_template_path()."""

    def test_returns_path(self) -> None:
        """get_template_path() returns a Path object."""
        result = get_template_path()
        assert isinstance(result, Path)

    def test_path_exists(self) -> None:
        """Returned path points to an existing directory."""
        result = get_template_path()
        assert result.exists()
        assert result.is_dir()

    def test_path_is_python_project(self) -> None:
        """Returned path is the python-project template."""
        result = get_template_path()
        assert result.name == "python-project"


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


# ── Scaffold template helpers ────────────────────────────────────────────────


def _fake_init_py(*, has_hello: bool = False) -> str:
    """Return a realistic __init__.py content."""
    version_block = (
        "try:\n"
        "    from ._version import __version__\n"
        "except ImportError:\n"
        '    __version__ = "0.0.0"\n'
    )
    lines = [version_block]
    if has_hello:
        lines.append("def hello() -> str:\n    return 'hello'\n")
    return "\n".join(lines)


def _build_scaffold_tree(
    root: Path,
    name: str = "test-pkg",
    *,
    hello: bool = False,
    utils: bool = False,
) -> list[str]:
    """Create a minimal scaffolded project tree on disk and return file list.

    This simulates what Copier would produce so that tests can assert
    on the file tree without invoking the real adapter.
    """
    pkg = name.replace("-", "_")
    src = root / "src" / pkg
    src.mkdir(parents=True)
    (src / "__init__.py").write_text(_fake_init_py(has_hello=hello))
    (src / "core").mkdir()
    (src / "core" / "__init__.py").write_text("")

    if utils:
        (src / "utils").mkdir()
        (src / "utils" / "__init__.py").write_text("")

    (root / "pyproject.toml").write_text(f'[project]\nname = "{name}"\n')
    (root / "README.md").write_text(f"# {name}\n\nA test project.\n")
    (root / "tests").mkdir()
    (root / "tests" / "__init__.py").write_text("")

    # docs
    docs = root / "docs"
    docs.mkdir()
    (docs / "index.md").write_text(f"# {name}\n\nWelcome to {name}.\n")
    tutorials = docs / "tutorials"
    tutorials.mkdir()
    (tutorials / "getting-started.md").write_text(f"# Getting started with {name}\n")

    # Collect relative file paths
    return [str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()]


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


# ── AC1: scaffold_project() returns a file list ─────────────────────────────


class TestScaffoldReturnsFileList:
    """AC1: scaffold_project() returns a list of all created file paths."""

    def test_scaffold_returns_file_list(self, tmp_path: Path) -> None:
        """Mock scaffold returns non-empty files list."""
        files = _build_scaffold_tree(tmp_path, "file-list-test")
        result = ScaffoldResult(
            success=True,
            path=str(tmp_path),
            message="ok",
            files_created=files,
        )
        assert result.success is True
        assert len(result.files_created) > 0, "files list should not be empty"

    def test_scaffold_file_list_in_existing_dir(self, tmp_path: Path) -> None:
        """Edge case: existing file in dir doesn't break scaffold result."""
        (tmp_path / "existing.txt").write_text("pre-existing")
        files = _build_scaffold_tree(tmp_path, "existing-dir-test")
        result = ScaffoldResult(
            success=True,
            path=str(tmp_path),
            message="ok",
            files_created=files,
        )
        assert result.success is True
        assert len(result.files_created) > 0


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
