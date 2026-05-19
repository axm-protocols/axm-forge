"""Split from ``test_core_callers.py``."""

from pathlib import Path

from axm_ast.core.callers import extract_calls
from axm_ast.core.parser import extract_module_info


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
