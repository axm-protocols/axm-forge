"""Split from ``test_call_extraction.py``."""

from pathlib import Path

import pytest

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.callers import find_callers


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


@pytest.fixture
def tiny_pkg(tmp_path: Path) -> Path:
    pkg = tmp_path / "p"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "a.py").write_text(
        "def foo():\n    return 1\n\ndef caller():\n    return foo()\n"
    )
    return pkg


def test_find_callers_still_works_after_helper_extraction(tiny_pkg: Path) -> None:
    info = analyze_package(tiny_pkg)
    results = find_callers(info, "foo")

    assert len(results) == 1
    assert results[0].symbol == "foo"


def test_find_callers_returns_empty_for_unused_symbol(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "mypkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "mod.py").write_text("def unused(): pass\n", encoding="utf-8")
    pkg = analyze_package(pkg_dir)

    callers = find_callers(pkg, "unused")

    assert callers == []
