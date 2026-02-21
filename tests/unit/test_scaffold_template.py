"""Tests for scaffold template output — verifies AXM-75 acceptance criteria."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from axm_init.cli import app

# Required args for scaffold
SCAFFOLD_ARGS = [
    "--org",
    "test-org",
    "--author",
    "Test Author",
    "--email",
    "test@test.com",
]


def _scaffold(tmp_path: Path, name: str, *, json_output: bool = False) -> Path:
    """Run scaffold and return the project directory."""
    args = [
        "scaffold",
        str(tmp_path),
        "--name",
        name,
        *SCAFFOLD_ARGS,
    ]
    if json_output:
        args.append("--json")
    f = io.StringIO()
    try:
        with redirect_stdout(f):
            app(args, exit_on_error=False)
    except SystemExit:
        pass
    return tmp_path


class TestScaffoldReturnsFileList:
    """AC1: scaffold_project() returns a list of all created file paths."""

    def test_scaffold_returns_file_list(self, tmp_path: Path) -> None:
        """Run scaffold and verify JSON output contains non-empty files list."""
        args = [
            "scaffold",
            str(tmp_path),
            "--name",
            "file-list-test",
            "--json",
            *SCAFFOLD_ARGS,
        ]
        f = io.StringIO()
        try:
            with redirect_stdout(f):
                app(args, exit_on_error=False)
        except SystemExit:
            pass

        data = json.loads(f.getvalue())
        assert data["success"] is True
        assert len(data["files"]) > 0, "files list should not be empty"

    def test_scaffold_file_list_in_existing_dir(self, tmp_path: Path) -> None:
        """Edge case: scaffold into dir with existing file returns correct list."""
        (tmp_path / "existing.txt").write_text("pre-existing")

        args = [
            "scaffold",
            str(tmp_path),
            "--name",
            "existing-dir-test",
            "--json",
            *SCAFFOLD_ARGS,
        ]
        f = io.StringIO()
        try:
            with redirect_stdout(f):
                app(args, exit_on_error=False)
        except SystemExit:
            pass

        data = json.loads(f.getvalue())
        assert data["success"] is True
        assert len(data["files"]) > 0


class TestScaffoldNoHello:
    """AC2: __init__.py template uses version import pattern (no hello())."""

    def test_scaffold_no_hello(self, tmp_path: Path) -> None:
        """Run scaffold, read __init__.py — no hello function present."""
        _scaffold(tmp_path, "clean-init-test")

        init_files = list(tmp_path.rglob("__init__.py"))
        # Find the package __init__.py (not tests/ or core/)
        pkg_init = [
            f for f in init_files if "src" in str(f) and f.parent.name != "core"
        ]
        assert len(pkg_init) >= 1, f"Expected package __init__.py, found: {init_files}"

        content = pkg_init[0].read_text()
        assert (
            "def hello" not in content
        ), f"hello() function should not be in __init__.py: {content}"

    def test_scaffold_version_import(self, tmp_path: Path) -> None:
        """Functional: __init__.py contains version import with try/except."""
        _scaffold(tmp_path, "ver-import-test")

        init_files = list(tmp_path.rglob("__init__.py"))
        pkg_init = [
            f for f in init_files if "src" in str(f) and f.parent.name != "core"
        ]
        assert len(pkg_init) >= 1

        content = pkg_init[0].read_text()
        assert "__version__" in content
        assert "try" in content, "Should use try/except for version import"


class TestScaffoldNoUtilsDir:
    """AC3: No utils/ directory created by default."""

    def test_scaffold_no_utils_dir(self, tmp_path: Path) -> None:
        """Run scaffold, check dir tree — no utils/ directory exists."""
        _scaffold(tmp_path, "no-utils-test")

        # Only check within src/ to avoid false positives from .venv
        src_dirs = list(tmp_path.rglob("src"))
        if src_dirs:
            utils_dirs = list(src_dirs[0].rglob("utils"))
            assert (
                len(utils_dirs) == 0
            ), f"utils/ should not exist in src/: {utils_dirs}"


class TestScaffoldDocsNoHello:
    """AC4: Doc templates use version/MCP example instead of hello()."""

    def test_scaffold_docs_no_hello(self, tmp_path: Path) -> None:
        """README, index.md, getting-started.md have no hello() reference."""
        _scaffold(tmp_path, "docs-test")

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
