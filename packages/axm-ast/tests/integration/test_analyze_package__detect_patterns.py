"""Split from ``test_build_context__format_context_json.py``.

Covers ``analyze_package`` + ``detect_patterns`` integration.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.context import detect_patterns

# ─── Helpers ──────────────────────────────────────────────────────────


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
class TestDetectPatterns:
    """Test project pattern detection."""

    def test_detect_patterns_all_exports(self, tmp_path: Path) -> None:
        """Counts modules with __all__."""
        pkg = _make_pkg(
            tmp_path,
            modules={
                "core.py": (
                    '"""Core."""\n'
                    '__all__ = ["foo"]\n'
                    "def foo() -> None:\n"
                    '    """Foo."""\n'
                    "    pass\n"
                ),
            },
        )
        from axm_ast.core.analyzer import analyze_package

        info = analyze_package(pkg)
        patterns = detect_patterns(info, tmp_path)
        assert patterns["all_exports_count"] == 1

    def test_detect_patterns_src_layout(self, tmp_path: Path) -> None:
        """Detects src/ layout."""
        src_dir = tmp_path / "src" / "mypkg"
        src_dir.mkdir(parents=True)
        (src_dir / "__init__.py").write_text('"""Pkg."""\n')
        from axm_ast.core.analyzer import analyze_package

        info = analyze_package(src_dir)
        patterns = detect_patterns(info, tmp_path)
        assert patterns["layout"] == "src"

    def test_detect_patterns_flat_layout(self, tmp_path: Path) -> None:
        """Detects flat layout."""
        pkg = _make_pkg(tmp_path)
        from axm_ast.core.analyzer import analyze_package

        info = analyze_package(pkg)
        patterns = detect_patterns(info, tmp_path)
        assert patterns["layout"] == "flat"

    def test_detect_patterns_test_naming(self, tmp_path: Path) -> None:
        """Detects test file naming convention."""
        pkg = _make_pkg(tmp_path)
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_core.py").write_text('"""Test."""\n')
        (tests_dir / "test_utils.py").write_text('"""Test."""\n')
        from axm_ast.core.analyzer import analyze_package

        info = analyze_package(pkg)
        patterns = detect_patterns(info, tmp_path)
        assert patterns["test_count"] == 2
