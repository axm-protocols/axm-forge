from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.analyzer import analyze_package
from axm_ast.formatters import format_compressed
from axm_ast.models.nodes import PackageInfo
from tests.integration._helpers import (
    _write_pyproject,
    _write_src_module,
    _write_test_modules,
)


@pytest.fixture
def pkg_without_tests(tmp_path: Path) -> PackageInfo:
    """Package with src/ only, no tests directory."""
    pkg_dir = tmp_path / "my_pkg"
    pkg_dir.mkdir()
    _write_pyproject(pkg_dir, "my_pkg")
    _write_src_module(pkg_dir, "my_pkg")
    return analyze_package(pkg_dir)


@pytest.fixture
def pkg_tests_only(tmp_path: Path) -> PackageInfo:
    """Package with only test modules, empty src."""
    pkg_dir = tmp_path / "my_pkg"
    pkg_dir.mkdir()
    _write_pyproject(pkg_dir, "my_pkg")
    src = pkg_dir / "src" / "my_pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    _write_test_modules(pkg_dir)
    return analyze_package(pkg_dir)


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_compress_excludes_test_modules(pkg_with_tests):
    """Compress output must not contain test_ symbols from tests/."""
    result = format_compressed(pkg_with_tests)
    assert "test_compute" not in result
    assert "TestEngine" not in result


def test_compress_includes_source_modules(pkg_with_tests):
    """Source modules must be present with signatures."""
    result = format_compressed(pkg_with_tests)
    assert "compute" in result
    assert "Engine" in result


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_compress_no_tests_directory(pkg_without_tests):
    """Package without tests/ works normally."""
    result = format_compressed(pkg_without_tests)
    assert "compute" in result
    assert "Engine" in result


def test_compress_tests_only_package(pkg_tests_only):
    """Package with only test modules produces minimal output."""
    result = format_compressed(pkg_tests_only)
    assert "test_compute" not in result
    assert "TestEngine" not in result
    # Only init module header expected at most
    content_lines = [ln for ln in result.strip().splitlines() if ln.strip()]
    assert len(content_lines) <= 5


def test_compress_conftest_excluded(pkg_with_tests):
    """conftest.py fixtures are excluded from compress output."""
    result = format_compressed(pkg_with_tests)
    assert "conftest" not in result
    assert "sample_input" not in result
