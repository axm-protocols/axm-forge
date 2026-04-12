"""Tests for CalleesTool and CLI callees command (AXM-406)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

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
        src_path = Path(__file__).parent.parent / "src" / "axm_ast"
        if not src_path.exists():
            return  # Skip if not in dev layout
        pkg = analyze_package(src_path)
        callees = find_callees(pkg, "trace_flow")
        symbols = [c.symbol for c in callees]
        assert "find_callees" in symbols
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


class TestCalleesMCPTool:
    """CalleesTool MCP wrapper returns ToolResult."""

    def test_mcp_tool_success(self, tmp_path: Path) -> None:
        from axm_ast.tools.callees import CalleesTool

        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": ("def helper():\n    pass\n\ndef main():\n    helper()\n"),
            },
        )
        tool = CalleesTool()
        result = tool.execute(path=str(pkg_path), symbol="main")
        assert result.success is True
        assert result.data is not None
        assert result.data["count"] >= 1
        callee = result.data["callees"][0]
        assert "call_expression" in callee
        assert "symbol" not in callee

    def test_mcp_tool_missing_symbol(self) -> None:
        from axm_ast.tools.callees import CalleesTool

        tool = CalleesTool()
        result = tool.execute(path=".")
        assert result.success is False
        assert "symbol" in (result.error or "").lower()


# ─── CLI tests ──────────────────────────────────────────────────────────────


class TestCalleesCLI:
    """CLI callees command integration tests."""

    def test_callees_json_output(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": ("def helper():\n    pass\n\ndef main():\n    helper()\n"),
            },
        )
        result = subprocess.run(
            [
                "uv",
                "run",
                "axm-ast",
                "callees",
                str(pkg_path),
                "--symbol",
                "main",
                "--json",
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        symbols = [c["symbol"] for c in data]
        assert "helper" in symbols

    def test_callees_no_results(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": "def noop():\n    x = 42\n",
            },
        )
        result = subprocess.run(
            ["uv", "run", "axm-ast", "callees", str(pkg_path), "--symbol", "noop"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        assert result.returncode == 0
        assert "No callees" in result.stdout or "📭" in result.stdout
