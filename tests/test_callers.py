"""TDD tests for caller/usage analysis — who calls what function."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.callers import extract_calls, find_callers
from axm_ast.core.parser import extract_module_info

FIXTURES = Path(__file__).parent / "fixtures"


# ─── Unit: extract_calls ─────────────────────────────────────────────────────


class TestExtractCalls:
    """Test call-site extraction from a single module."""

    def test_simple_function_call(self, tmp_path: Path) -> None:
        """Detects a simple function call."""
        f = tmp_path / "mod.py"
        f.write_text('"""Mod."""\ndef setup() -> None:\n    """Set up."""\n    foo()\n')
        mod = extract_module_info(f)
        calls = extract_calls(mod)
        names = [c.symbol for c in calls]
        assert "foo" in names

    def test_method_call(self, tmp_path: Path) -> None:
        """Detects a method call like self.bar()."""
        f = tmp_path / "mod.py"
        f.write_text(
            '"""Mod."""\n'
            "class X:\n"
            '    """X."""\n'
            "    def run(self) -> None:\n"
            '        """Run."""\n'
            "        self.bar()\n"
        )
        mod = extract_module_info(f)
        calls = extract_calls(mod)
        names = [c.symbol for c in calls]
        assert "bar" in names

    def test_chained_call(self, tmp_path: Path) -> None:
        """Detects the last name in a chained call a.b.c()."""
        f = tmp_path / "mod.py"
        f.write_text('"""Mod."""\ndef go() -> None:\n    """Go."""\n    a.b.c()\n')
        mod = extract_module_info(f)
        calls = extract_calls(mod)
        names = [c.symbol for c in calls]
        assert "c" in names

    def test_call_with_args(self, tmp_path: Path) -> None:
        """Call expression text includes arguments."""
        f = tmp_path / "mod.py"
        f.write_text(
            '"""Mod."""\ndef go() -> None:\n    """Go."""\n    greet("world", 42)\n'
        )
        mod = extract_module_info(f)
        calls = extract_calls(mod)
        greet_calls = [c for c in calls if c.symbol == "greet"]
        assert len(greet_calls) == 1
        assert "world" in greet_calls[0].call_expression

    def test_nested_calls(self, tmp_path: Path) -> None:
        """Nested calls foo(bar()) produce 2 CallSites."""
        f = tmp_path / "mod.py"
        f.write_text('"""Mod."""\ndef go() -> None:\n    """Go."""\n    foo(bar())\n')
        mod = extract_module_info(f)
        calls = extract_calls(mod)
        names = [c.symbol for c in calls]
        assert "foo" in names
        assert "bar" in names

    def test_no_calls(self, tmp_path: Path) -> None:
        """Module with no calls returns empty list."""
        f = tmp_path / "mod.py"
        f.write_text('"""Mod."""\nx = 42\n')
        mod = extract_module_info(f)
        calls = extract_calls(mod)
        assert calls == []

    def test_call_line_number(self, tmp_path: Path) -> None:
        """Call site reports correct line number."""
        f = tmp_path / "mod.py"
        f.write_text('"""Mod."""\n# comment\n# comment\nfoo()\n')
        mod = extract_module_info(f)
        calls = extract_calls(mod)
        assert calls[0].line == 4

    def test_context_is_enclosing_function(self, tmp_path: Path) -> None:
        """Context field captures enclosing function name."""
        f = tmp_path / "mod.py"
        f.write_text('"""Mod."""\ndef main() -> None:\n    """Entry."""\n    setup()\n')
        mod = extract_module_info(f)
        calls = extract_calls(mod)
        assert calls[0].context == "main"

    def test_context_toplevel(self, tmp_path: Path) -> None:
        """Top-level call has context None."""
        f = tmp_path / "mod.py"
        f.write_text('"""Mod."""\nsetup()\n')
        mod = extract_module_info(f)
        calls = extract_calls(mod)
        assert calls[0].context is None


# ─── Unit: find_callers ──────────────────────────────────────────────────────


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
        assert len(results) >= 1
        assert any(r.symbol == "greet" for r in results)

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

    def test_method_call_found(self, tmp_path: Path) -> None:
        """Method calls like obj.add() are found for 'add'."""
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Pkg."""\n'
            "class Calc:\n"
            '    """Calc."""\n'
            "    def add(self, a: int) -> int:\n"
            '        """Add."""\n'
            "        return a\n"
        )
        (pkg_dir / "use.py").write_text(
            '"""Use."""\n'
            "def main() -> None:\n"
            '    """Main."""\n'
            "    c = Calc()\n"
            "    c.add(1)\n"
        )
        pkg = analyze_package(pkg_dir)
        results = find_callers(pkg, "add")
        assert len(results) >= 1

    def test_context_captured(self, tmp_path: Path) -> None:
        """Caller captures enclosing function name."""
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Pkg."""\ndef wrapper() -> None:\n    """Wrap."""\n    target()\n'
        )
        pkg = analyze_package(pkg_dir)
        results = find_callers(pkg, "target")
        assert results[0].context == "wrapper"

    def test_recursive_call(self, tmp_path: Path) -> None:
        """Recursive calls are detected."""
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Pkg."""\n'
            "def recurse(n: int) -> int:\n"
            '    """Recurse."""\n'
            "    return recurse(n - 1)\n"
        )
        pkg = analyze_package(pkg_dir)
        results = find_callers(pkg, "recurse")
        assert len(results) >= 1


# ─── Edge cases ──────────────────────────────────────────────────────────────


class TestCallerEdgeCases:
    """Edge cases for caller analysis."""

    def test_call_in_decorator(self, tmp_path: Path) -> None:
        """Call inside a decorator expression is captured."""
        f = tmp_path / "mod.py"
        f.write_text(
            '"""Mod."""\n'
            "@app.route('/foo')\n"
            "def handler() -> None:\n"
            '    """Handle."""\n'
            "    pass\n"
        )
        mod = extract_module_info(f)
        calls = extract_calls(mod)
        names = [c.symbol for c in calls]
        assert "route" in names

    def test_call_in_comprehension(self, tmp_path: Path) -> None:
        """Call inside a list comprehension is captured."""
        f = tmp_path / "mod.py"
        f.write_text(
            '"""Mod."""\n'
            "def go() -> None:\n"
            '    """Go."""\n'
            "    xs = [f(x) for x in items]\n"
        )
        mod = extract_module_info(f)
        calls = extract_calls(mod)
        names = [c.symbol for c in calls]
        assert "f" in names

    def test_lambda_call(self, tmp_path: Path) -> None:
        """Call inside a lambda is captured."""
        f = tmp_path / "mod.py"
        f.write_text('"""Mod."""\nfn = lambda x: process(x)\n')
        mod = extract_module_info(f)
        calls = extract_calls(mod)
        names = [c.symbol for c in calls]
        assert "process" in names


# ─── Functional: CLI integration ─────────────────────────────────────────────


class TestCallersCLI:
    """Test the CLI callers command."""

    def test_callers_text_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """CLI prints caller locations."""
        from axm_ast.cli import app

        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Pkg."""\ndef target() -> None:\n    """Target."""\n    pass\n'
        )
        (pkg_dir / "user.py").write_text(
            '"""User."""\ndef main() -> None:\n    """Main."""\n    target()\n'
        )
        with pytest.raises(SystemExit):
            app(["callers", str(pkg_dir), "--symbol", "target"])
        captured = capsys.readouterr()
        assert "target" in captured.out

    def test_callers_json_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """CLI --json returns structured list."""
        import json

        from axm_ast.cli import app

        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Pkg."""\ndef target() -> None:\n    """Target."""\n    pass\n'
        )
        (pkg_dir / "user.py").write_text(
            '"""User."""\ndef main() -> None:\n    """Main."""\n    target()\n'
        )
        with pytest.raises(SystemExit):
            app(["callers", str(pkg_dir), "--symbol", "target", "--json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_callers_no_results(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Symbol with no callers prints message."""
        from axm_ast.cli import app

        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Pkg."""\ndef lonely() -> None:\n    """Lonely."""\n    pass\n'
        )
        with pytest.raises(SystemExit):
            app(["callers", str(pkg_dir), "--symbol", "lonely"])
        captured = capsys.readouterr()
        assert "no callers" in captured.out.lower() or "0" in captured.out
