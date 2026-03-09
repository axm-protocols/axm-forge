"""TDD tests for axm-ast execution flow tracing and entry point detection."""

from __future__ import annotations

from pathlib import Path

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.flows import (
    EntryPoint,
    find_callees,
    find_entry_points,
    format_flows,
    trace_flow,
)

# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    """Create a package from file dict and return path."""
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    for name, content in files.items():
        filepath = pkg / name
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content)
    return pkg


# ─── Unit: entry point detection ─────────────────────────────────────────────


class TestDetectCycloptsEntry:
    """cyclopts @app.default and @app.command decorators."""

    def test_detect_cyclopts_entry(self, tmp_path: Path) -> None:
        """Module with @app.default → detected as entry point."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "cli.py": (
                    "import cyclopts\n"
                    "app = cyclopts.App()\n\n"
                    "@app.default\n"
                    "def main():\n"
                    "    pass\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        entries = find_entry_points(pkg)
        entry_names = {e.name for e in entries}
        assert "main" in entry_names
        main_entry = next(e for e in entries if e.name == "main")
        assert main_entry.framework == "cyclopts"
        assert main_entry.kind == "decorator"


class TestDetectClickEntry:
    """click @click.command decorator."""

    def test_detect_click_entry(self, tmp_path: Path) -> None:
        """Module with @click.command → detected."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "cli.py": (
                    "import click\n\n@click.command()\ndef hello():\n    pass\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        entries = find_entry_points(pkg)
        entry_names = {e.name for e in entries}
        assert "hello" in entry_names
        hello = next(e for e in entries if e.name == "hello")
        assert hello.framework == "click"


class TestDetectFlaskRoute:
    """Flask @app.route decorator."""

    def test_detect_flask_route(self, tmp_path: Path) -> None:
        """Module with @app.route("/api") → detected."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "routes.py": (
                    "from flask import Flask\n"
                    "app = Flask(__name__)\n\n"
                    "@app.route('/api')\n"
                    "def index():\n"
                    "    return 'hello'\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        entries = find_entry_points(pkg)
        entry_names = {e.name for e in entries}
        assert "index" in entry_names
        index = next(e for e in entries if e.name == "index")
        assert index.framework == "flask"


class TestDetectFastapiRoute:
    """FastAPI @app.get decorator."""

    def test_detect_fastapi_route(self, tmp_path: Path) -> None:
        """Module with @app.get("/items") → detected."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "api.py": (
                    "from fastapi import FastAPI\n"
                    "app = FastAPI()\n\n"
                    "@app.get('/items')\n"
                    "def get_items():\n"
                    "    return []\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        entries = find_entry_points(pkg)
        entry_names = {e.name for e in entries}
        assert "get_items" in entry_names
        ep = next(e for e in entries if e.name == "get_items")
        assert ep.framework == "fastapi"


class TestDetectPytestFunction:
    """pytest test_* prefix detection."""

    def test_detect_pytest_function(self, tmp_path: Path) -> None:
        """Function named test_foo → detected as pytest entry."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "test_core.py": "def test_foo():\n    assert True\n",
            },
        )
        pkg = analyze_package(pkg_path)
        entries = find_entry_points(pkg)
        entry_names = {e.name for e in entries}
        assert "test_foo" in entry_names
        ep = next(e for e in entries if e.name == "test_foo")
        assert ep.framework == "pytest"


class TestDetectMainGuard:
    """if __name__ == '__main__' detection."""

    def test_detect_main_guard(self, tmp_path: Path) -> None:
        """if __name__ == '__main__' block → detected."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "app.py": (
                    "def main():\n    pass\n\nif __name__ == '__main__':\n    main()\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        entries = find_entry_points(pkg)
        main_guards = [e for e in entries if e.kind == "main_guard"]
        assert len(main_guards) == 1
        assert main_guards[0].framework == "main"


class TestIgnoreRegularFunction:
    """Plain functions should not be detected."""

    def test_ignore_regular_function(self, tmp_path: Path) -> None:
        """Plain function def helper() → not detected."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "utils.py": "def helper():\n    pass\n",
            },
        )
        pkg = analyze_package(pkg_path)
        entries = find_entry_points(pkg)
        entry_names = {e.name for e in entries}
        assert "helper" not in entry_names


# ─── Unit: callee resolution ────────────────────────────────────────────────


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


# ─── Unit: trace_flow BFS ───────────────────────────────────────────────────


class TestTraceFlowLinear:
    """Test BFS flow tracing — linear chain."""

    def test_trace_flow_linear(self, tmp_path: Path) -> None:
        """A → B → C chain → returns [A, B, C] with depths."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "chain.py": (
                    "def func_c():\n"
                    "    pass\n\n"
                    "def func_b():\n"
                    "    func_c()\n\n"
                    "def func_a():\n"
                    "    func_b()\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        steps = trace_flow(pkg, "func_a")
        names = [s.name for s in steps]
        assert names == ["func_a", "func_b", "func_c"]
        assert steps[0].depth == 0
        assert steps[1].depth == 1
        assert steps[2].depth == 2


class TestTraceFlowBranching:
    """Test BFS flow tracing — branching calls."""

    def test_trace_flow_branching(self, tmp_path: Path) -> None:
        """A → B, A → C → returns both branches."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "branch.py": (
                    "def func_b():\n"
                    "    pass\n\n"
                    "def func_c():\n"
                    "    pass\n\n"
                    "def func_a():\n"
                    "    func_b()\n"
                    "    func_c()\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        steps = trace_flow(pkg, "func_a")
        names = {s.name for s in steps}
        assert "func_a" in names
        assert "func_b" in names
        assert "func_c" in names
        # Both B and C should be at depth 1
        for s in steps:
            if s.name in {"func_b", "func_c"}:
                assert s.depth == 1


# ─── Functional tests ───────────────────────────────────────────────────────


class TestFlowsSamplePkg:
    """Functional test with test fixtures."""

    def test_flows_sample_pkg(self, tmp_path: Path) -> None:
        """Run on a sample package → known entry points detected."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": '__all__ = ["greet"]\n\nfrom .core import greet\n',
                "core.py": (
                    "def greet(name: str) -> str:\n"
                    "    return f'Hello, {name}'\n\n"
                    "def _helper():\n"
                    "    pass\n"
                ),
                "test_core.py": (
                    "from .core import greet\n\n"
                    "def test_greet():\n"
                    "    assert greet('x') == 'Hello, x'\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        entries = find_entry_points(pkg)
        entry_names = {e.name for e in entries}
        # __all__ exports and test functions
        assert "greet" in entry_names
        assert "test_greet" in entry_names
        assert "_helper" not in entry_names


class TestFlowsDogfood:
    """Functional test — dogfooding on axm-ast itself."""

    def test_flows_dogfood(self) -> None:
        """Run on axm-ast itself → CLI entry points detected."""
        src_path = Path(__file__).parent.parent / "src" / "axm_ast"
        if not src_path.exists():
            return  # Skip if not in dev layout
        pkg = analyze_package(src_path)
        entries = find_entry_points(pkg)
        # Should detect at least test functions or __all__ exports
        assert len(entries) > 0
        frameworks = {e.framework for e in entries}
        # axm-ast has __all__ exports
        assert "all" in frameworks


# ─── Edge cases ──────────────────────────────────────────────────────────────


class TestEdgeNoEntryPoints:
    """Library with zero frameworks."""

    def test_no_entry_points(self, tmp_path: Path) -> None:
        """No decorators, no tests, no main guard → empty list."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "lib.py": "def compute(x):\n    return x * 2\n",
            },
        )
        pkg = analyze_package(pkg_path)
        entries = find_entry_points(pkg)
        assert entries == []


class TestEdgeCircularCalls:
    """Circular call chains must terminate."""

    def test_circular_calls(self, tmp_path: Path) -> None:
        """A → B → A → flow tracing terminates (visited set)."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "circular.py": (
                    "def func_a():\n    func_b()\n\ndef func_b():\n    func_a()\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        steps = trace_flow(pkg, "func_a")
        names = [s.name for s in steps]
        # Should visit A and B but not loop
        assert "func_a" in names
        assert "func_b" in names
        assert len(steps) == 2


class TestEdgeMaxDepth:
    """Very deep call chain stops at configurable depth."""

    def test_max_depth(self, tmp_path: Path) -> None:
        """Chain of 10 functions, max_depth=3 → stops early."""
        # Build a → b → c → d → e → f → g → h → i → j
        funcs = []
        for i in range(10):
            name = f"func_{chr(ord('a') + i)}"
            next_name = f"func_{chr(ord('a') + i + 1)}" if i < 9 else None
            if next_name:
                funcs.append(f"def {name}():\n    {next_name}()\n")
            else:
                funcs.append(f"def {name}():\n    pass\n")

        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "deep.py": "\n".join(funcs),
            },
        )
        pkg = analyze_package(pkg_path)
        steps = trace_flow(pkg, "func_a", max_depth=3)
        # Should have at most 4 entries (depth 0, 1, 2, 3)
        assert len(steps) <= 4
        depths = {s.depth for s in steps}
        assert max(depths) <= 3


class TestEdgeDynamicCalls:
    """Dynamic calls should not be detected (conservative)."""

    def test_dynamic_calls(self, tmp_path: Path) -> None:
        """getattr(obj, name)() → not detected as entry point."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "dynamic.py": (
                    "def dispatch(obj, name):\n    return getattr(obj, name)()\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        entries = find_entry_points(pkg)
        # dispatch is not a framework entry point
        assert not any(e.name == "dispatch" and e.kind == "decorator" for e in entries)


class TestEdgeDecoratedNonEntry:
    """@property, @staticmethod are not entry point decorators."""

    def test_decorated_non_entry(self, tmp_path: Path) -> None:
        """@property, @staticmethod → not flagged as entry point."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "models.py": (
                    "class Foo:\n"
                    "    @property\n"
                    "    def bar(self):\n"
                    "        return 42\n\n"
                    "    @staticmethod\n"
                    "    def baz():\n"
                    "        return 0\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        entries = find_entry_points(pkg)
        # property and staticmethod are NOT framework entry points
        entry_names = {e.name for e in entries if e.kind == "decorator"}
        assert "bar" not in entry_names
        assert "baz" not in entry_names


# ─── Formatting ──────────────────────────────────────────────────────────────


class TestFormatFlows:
    """Test output formatting."""

    def test_format_empty(self) -> None:
        """Empty results → clean message."""
        assert format_flows([]) == "✅ No entry points detected."

    def test_format_results(self) -> None:
        """Results → grouped output."""
        entries = [
            EntryPoint(
                name="index",
                module="routes",
                kind="decorator",
                line=5,
                framework="flask",
            ),
            EntryPoint(
                name="test_foo",
                module="tests",
                kind="test",
                line=1,
                framework="pytest",
            ),
        ]
        output = format_flows(entries)
        assert "2 entry point(s)" in output
        assert "flask" in output
        assert "pytest" in output
        assert "index" in output
        assert "test_foo" in output
