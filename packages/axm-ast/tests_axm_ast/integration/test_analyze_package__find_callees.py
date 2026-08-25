"""Tests for CalleesTool and CLI callees command (AXM-406).

Also includes tests split from ``test_analyze_package__trace_flow.py``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.flows import find_callees

# ─── Helpers ────────────────────────────────────────────────────────────────


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    """Create a temporary Python package from file name → content mapping."""
    pkg = tmp_path / "mypkg"
    for name, content in files.items():
        fp = pkg / name
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return pkg


# ─── Unit tests (ticket spec) ──────────────────────────────────────────────


class TestCalleesToolBasic:
    """Sample project with main() calling helper() — tool returns CallSite."""

    def test_callees_tool_basic(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": ("def helper():\n    pass\n\ndef main():\n    helper()\n"),
            },
        )
        pkg = analyze_package(pkg_path)
        callees = find_callees(pkg, "main")
        symbols = [c.symbol for c in callees]
        assert "helper" in symbols


class TestCalleesToolEmpty:
    """Function with no calls — returns empty list."""

    def test_callees_tool_empty(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": ("def noop():\n    x = 42\n"),
            },
        )
        pkg = analyze_package(pkg_path)
        callees = find_callees(pkg, "noop")
        assert callees == []


class TestCalleesToolMethod:
    """Class method calling other methods."""

    def test_callees_tool_method(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": (
                    "class Foo:\n"
                    "    def bar(self):\n"
                    "        self.baz()\n"
                    "        self.qux()\n\n"
                    "    def baz(self):\n"
                    "        pass\n\n"
                    "    def qux(self):\n"
                    "        pass\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        callees = find_callees(pkg, "bar")
        symbols = [c.symbol for c in callees]
        assert "baz" in symbols
        assert "qux" in symbols


# ─── Functional tests ──────────────────────────────────────────────────────


class TestCalleesDogfood:
    """Run on axm-ast itself — trace_flow has known callees."""

    def test_callees_dogfood(self) -> None:
        src_path = Path(__file__).parent.parent.parent / "src" / "axm_ast"
        if not src_path.exists():
            return  # Skip if not in dev layout
        pkg = analyze_package(src_path)
        callees = find_callees(pkg, "trace_flow")
        symbols = [c.symbol for c in callees]
        assert "_get_callees" in symbols
        assert "_find_symbol_location" in symbols


# ─── Edge cases ─────────────────────────────────────────────────────────────


class TestCalleesSymbolNotFound:
    """Non-existent symbol — should return empty list."""

    def test_symbol_not_found(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": "def hello():\n    pass\n",
            },
        )
        pkg = analyze_package(pkg_path)
        callees = find_callees(pkg, "nonexistent_function")
        assert callees == []


# ─── Split from test_analyze_package__trace_flow.py ─────────────────────────


class TestFindCallees:
    """Test find_callees — forward call graph."""

    def test_find_callees_simple(self, tmp_path: Path) -> None:
        """Function calling 3 other functions → returns 3 callees."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": (
                    "def alpha():\n"
                    "    pass\n\n"
                    "def beta():\n"
                    "    pass\n\n"
                    "def gamma():\n"
                    "    pass\n\n"
                    "def main():\n"
                    "    alpha()\n"
                    "    beta()\n"
                    "    gamma()\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        callees = find_callees(pkg, "main")
        callee_names = {c.symbol for c in callees}
        assert callee_names == {"alpha", "beta", "gamma"}


class TestFindCalleesNoReparse:
    """find_callees does not re-parse the same file twice."""

    def test_no_reparse_with_cache(self, tmp_path: Path) -> None:
        """Each file read at most once when using _parse_cache."""

        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": ("def alpha():\n    pass\n\ndef main():\n    alpha()\n"),
            },
        )
        pkg = analyze_package(pkg_path)

        read_count: dict[str, int] = {}
        original_read_text = Path.read_text

        def counting_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
            key = str(self)
            read_count[key] = read_count.get(key, 0) + 1
            return original_read_text(self, *args, **kwargs)

        cache: dict[str, tuple[Any, str]] = {}
        with patch.object(Path, "read_text", counting_read_text):
            # Call twice with the same cache
            find_callees(pkg, "main", _parse_cache=cache)
            find_callees(pkg, "alpha", _parse_cache=cache)

        # Each file should be read at most once
        for path_str, count in read_count.items():
            if path_str.endswith(".py"):
                assert count <= 1, f"{path_str} was read {count} times"
