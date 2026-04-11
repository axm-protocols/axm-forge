from __future__ import annotations

import json
from pathlib import Path

import pytest

from axm_ast.core.analyzer import analyze_package
from axm_ast.formatters import format_compressed, format_json
from axm_ast.models.nodes import PackageInfo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_src_module(pkg_dir: Path, pkg_name: str) -> None:
    """Create a source module with a public function and class."""
    src = pkg_dir / "src" / pkg_name
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "core.py").write_text(
        "from __future__ import annotations\n\n"
        "def compute(x: int) -> int:\n"
        '    """Compute something."""\n'
        "    return x * 2\n\n"
        "class Engine:\n"
        '    """Main engine."""\n'
        "    def run(self) -> None:\n"
        "        pass\n"
    )


def _write_test_modules(pkg_dir: Path) -> None:
    """Create test modules with test functions and a test class."""
    tests = pkg_dir / "tests"
    tests.mkdir(exist_ok=True)
    (tests / "__init__.py").write_text("")
    (tests / "test_core.py").write_text(
        "from __future__ import annotations\n\n"
        "def test_compute_doubles():\n"
        "    assert 2 * 2 == 4\n\n"
        "def test_compute_zero():\n"
        "    assert 0 * 2 == 0\n\n"
        "class TestEngine:\n"
        "    def test_run(self):\n"
        "        pass\n"
    )
    (tests / "conftest.py").write_text(
        "from __future__ import annotations\n\n"
        "import pytest\n\n"
        "@pytest.fixture\n"
        "def sample_input():\n"
        "    return 42\n"
    )


def _write_pyproject(pkg_dir: Path, pkg_name: str) -> None:
    (pkg_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{pkg_name}"\nversion = "0.1.0"\n'
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def pkg_with_tests(tmp_path: Path) -> PackageInfo:
    """Package with both src/ and tests/ directories."""
    pkg_dir = tmp_path / "my_pkg"
    pkg_dir.mkdir()
    _write_pyproject(pkg_dir, "my_pkg")
    _write_src_module(pkg_dir, "my_pkg")
    _write_test_modules(pkg_dir)
    return analyze_package(pkg_dir)


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
# Functional tests
# ---------------------------------------------------------------------------


def test_compress_smaller_than_summary(pkg_with_tests):
    """Compressed output must be smaller than JSON summary."""
    compressed = format_compressed(pkg_with_tests)
    summary = format_json(pkg_with_tests, detail="summary")
    assert len(compressed) <= len(json.dumps(summary))


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
