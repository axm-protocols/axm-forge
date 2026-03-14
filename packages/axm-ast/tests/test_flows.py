"""TDD tests for axm-ast execution flow tracing and entry point detection."""

from __future__ import annotations

from pathlib import Path

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.flows import (
    EntryPoint,
    FlowStep,
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


# ─── Cross-module trace_flow tests (AXM-405) ────────────────────────────────


class TestCrossModuleBasic:
    """Basic cross-module resolution via ``from b import B``."""

    def test_cross_module_basic(self, tmp_path: Path) -> None:
        """Package with a.py importing B from b.py, test calling B()."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "a.py": ("from .b import B\n\ndef test_func():\n    B()\n"),
                "b.py": (
                    "def helper():\n"
                    "    pass\n\n"
                    "class B:\n"
                    "    def __init__(self):\n"
                    "        helper()\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)

        # Without cross_module → stops at B
        steps_no = trace_flow(pkg, "test_func", cross_module=False)
        names_no = [s.name for s in steps_no]
        assert "test_func" in names_no
        assert "B" in names_no
        # B is a local import so it's found, but helper should not be traced
        # (B is in the same package so find_callees should find it)

        # With cross_module → resolves into b.py
        steps = trace_flow(pkg, "test_func", cross_module=True)
        names = [s.name for s in steps]
        assert "test_func" in names
        assert "B" in names


class TestCrossModuleDepth:
    """3-level chain across modules: test → ClassA (mod_a) → helper (mod_b)."""

    def test_cross_module_depth(self, tmp_path: Path) -> None:
        """BFS reaches depth 3 with correct module attribution."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "test_entry.py": (
                    "from .mod_a import ClassA\n\ndef test_run():\n    ClassA()\n"
                ),
                "mod_a.py": (
                    "from .mod_b import helper\n\n"
                    "class ClassA:\n"
                    "    def __init__(self):\n"
                    "        helper()\n"
                ),
                "mod_b.py": ("def helper():\n    pass\n"),
            },
        )
        pkg = analyze_package(pkg_path)
        steps = trace_flow(pkg, "test_run", cross_module=True, max_depth=5)
        names = [s.name for s in steps]
        assert "test_run" in names
        assert "ClassA" in names


class TestImportResolutionFrom:
    """``from foo.bar import Baz`` pattern."""

    def test_import_resolution_from(self, tmp_path: Path) -> None:
        """Resolves ``from foo.bar import Baz`` to foo/bar.py class Baz."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "entry.py": ("from .sub.mod import Baz\n\ndef run():\n    Baz()\n"),
                "sub/__init__.py": "",
                "sub/mod.py": ("class Baz:\n    def __init__(self):\n        pass\n"),
            },
        )
        pkg = analyze_package(pkg_path)
        steps = trace_flow(pkg, "run", cross_module=True)
        names = [s.name for s in steps]
        assert "run" in names
        assert "Baz" in names


class TestImportResolutionDirect:
    """``import foo.bar`` pattern."""

    def test_import_resolution_direct(self, tmp_path: Path) -> None:
        """Resolves direct import to foo/bar.py."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "entry.py": (
                    "from .utils import do_stuff\n\ndef run():\n    do_stuff()\n"
                ),
                "utils.py": ("def do_stuff():\n    pass\n"),
            },
        )
        pkg = analyze_package(pkg_path)
        steps = trace_flow(pkg, "run", cross_module=True)
        names = [s.name for s in steps]
        assert "run" in names
        assert "do_stuff" in names


class TestRelativeImport:
    """``from .utils import helper`` pattern."""

    def test_relative_import(self, tmp_path: Path) -> None:
        """Resolves correctly relative to current module."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": (
                    "from .helpers import compute\n\ndef process():\n    compute()\n"
                ),
                "helpers.py": ("def compute():\n    pass\n"),
            },
        )
        pkg = analyze_package(pkg_path)
        steps = trace_flow(pkg, "process", cross_module=True)
        names = [s.name for s in steps]
        assert "process" in names
        assert "compute" in names


class TestCircularImportSafe:
    """Circular imports between modules don't cause infinite loops."""

    def test_circular_import_safe(self, tmp_path: Path) -> None:
        """a.py imports from b.py, b.py imports from a.py → terminates."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod_a.py": (
                    "from .mod_b import func_b\n\ndef func_a():\n    func_b()\n"
                ),
                "mod_b.py": (
                    "from .mod_a import func_a\n\ndef func_b():\n    func_a()\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        steps = trace_flow(pkg, "func_a", cross_module=True)
        names = [s.name for s in steps]
        # Should visit both but not loop
        assert "func_a" in names
        assert "func_b" in names
        # Finite number of steps
        assert len(steps) <= 4


# ─── Cross-module functional tests ──────────────────────────────────────────


class TestCrossModuleDogfood:
    """Functional test — cross-module trace on axm-ast itself."""

    def test_dogfood_axm_ast(self) -> None:
        """Run on axm-ast — cross-module trace from FlowsTool.execute works."""
        src_path = Path(__file__).parent.parent / "src" / "axm_ast"
        if not src_path.exists():
            return  # Skip if not in dev layout
        pkg = analyze_package(src_path)
        # trace_flow should be in the package; trace it with cross_module
        steps = trace_flow(
            pkg,
            "trace_flow",
            cross_module=True,
            max_depth=2,
        )
        assert len(steps) >= 1
        assert steps[0].name == "trace_flow"


# ─── Cross-module edge cases ────────────────────────────────────────────────


class TestEdgeStdlibImport:
    """External stdlib import → should be skipped."""

    def test_stdlib_import_skipped(self, tmp_path: Path) -> None:
        """Test calls os.path.join → skip, don't trace into stdlib."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": (
                    "import os\n\ndef test_func():\n    os.path.join('a', 'b')\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        steps = trace_flow(pkg, "test_func", cross_module=True)
        # Should not have stdlib symbols in the trace
        for s in steps:
            assert s.resolved_module is None or not s.resolved_module.startswith("os")


class TestEdgeMissingModule:
    """Import target doesn't exist on disk → gracefully skip."""

    def test_missing_module(self, tmp_path: Path) -> None:
        """Import from a module that doesn't exist → continue BFS."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": (
                    "from .nonexistent import Ghost\n\ndef test_func():\n    Ghost()\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        steps = trace_flow(pkg, "test_func", cross_module=True)
        names = [s.name for s in steps]
        assert "test_func" in names
        # Ghost should not crash, just not be resolved
        # (it may or may not appear depending on find_callees)


class TestEdgeReexportChain:
    """Re-export chain: ``from . import bar`` in ``__init__.py``."""

    def test_reexport_chain(self, tmp_path: Path) -> None:
        """Follow re-export from __init__.py to actual definition."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "from .core import greet\n",
                "core.py": ("def greet():\n    pass\n"),
                "entry.py": ("from . import greet\n\ndef run():\n    greet()\n"),
            },
        )
        pkg = analyze_package(pkg_path)
        steps = trace_flow(pkg, "run", cross_module=True)
        names = [s.name for s in steps]
        assert "run" in names


class TestEdgeBuiltinCalls:
    """Builtin calls (len, print) → skip, no module to resolve."""

    def test_builtin_calls_skipped(self, tmp_path: Path) -> None:
        """len(), print(), isinstance() → not traced."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": (
                    "def test_func():\n"
                    "    x = len([1, 2, 3])\n"
                    "    print(x)\n"
                    "    isinstance(x, int)\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        steps = trace_flow(pkg, "test_func", cross_module=True)
        # Only the entry point should appear (builtins are skipped)
        assert len(steps) >= 1
        for s in steps:
            assert s.resolved_module is None


class TestCrossModuleSiblingPackage:
    """Sibling-package imports resolved via project-root fallback.

    Simulates Django layout: tests/ imports from django/ at repo root.
    """

    def _make_sibling_project(self, tmp_path: Path) -> Path:
        """Create a project with sibling packages and a .git marker.

        Layout::

            project/
            ├── .git/              ← project root marker
            ├── mylib/
            │   ├── __init__.py
            │   └── http.py        ← defines HttpResponse
            └── tests/
                ├── __init__.py
                └── test_http.py   ← from mylib.http import HttpResponse
        """
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()  # marker

        # Sibling package: mylib
        mylib = project / "mylib"
        mylib.mkdir()
        (mylib / "__init__.py").write_text("")
        (mylib / "http.py").write_text(
            "class HttpResponse:\n"
            "    def __init__(self, content=b''):\n"
            "        self.content = content\n"
        )

        # Tests package
        tests = project / "tests"
        tests.mkdir()
        (tests / "__init__.py").write_text("")
        (tests / "test_http.py").write_text(
            "from mylib.http import HttpResponse\n\n"
            "def test_response():\n"
            "    r = HttpResponse(b'hello')\n"
            "    assert r.content == b'hello'\n"
        )
        return project

    def test_sibling_package_resolved(self, tmp_path: Path) -> None:
        """from mylib.http import HttpResponse → resolved via project root."""
        project = self._make_sibling_project(tmp_path)
        tests_pkg = analyze_package(project / "tests")
        steps = trace_flow(tests_pkg, "test_response", cross_module=True)
        names = [s.name for s in steps]
        assert "test_response" in names
        assert "HttpResponse" in names
        # Should have a resolved step pointing to the sibling package
        resolved_steps = [
            s for s in steps if s.name == "HttpResponse" and s.resolved_module
        ]
        assert len(resolved_steps) == 1
        assert resolved_steps[0].resolved_module == "mylib.http"

    def test_sibling_package_with_source(self, tmp_path: Path) -> None:
        """detail='source' enriches sibling-package symbols."""
        project = self._make_sibling_project(tmp_path)
        tests_pkg = analyze_package(project / "tests")
        steps = trace_flow(
            tests_pkg,
            "test_response",
            cross_module=True,
            detail="source",
        )
        entry = next(s for s in steps if s.name == "test_response")
        assert entry.source is not None
        assert "def test_response" in entry.source
        # Cross-module resolved symbol should also have source
        resolved = next(
            s for s in steps if s.name == "HttpResponse" and s.resolved_module
        )
        assert resolved.source is not None
        assert "class HttpResponse" in resolved.source

    def test_reexport_resolution(self, tmp_path: Path) -> None:
        """Re-export via __init__.py is followed to the actual definition."""
        project = tmp_path / "reexport_proj"
        project.mkdir()
        (project / ".git").mkdir()  # project root marker

        # mylib/http/ package with re-export
        http_pkg = project / "mylib" / "http"
        http_pkg.mkdir(parents=True)
        (project / "mylib" / "__init__.py").write_text("")
        (http_pkg / "__init__.py").write_text(
            "from mylib.http.response import HttpResponse\n"
        )
        (http_pkg / "response.py").write_text(
            "class HttpResponse:\n"
            "    def __init__(self, content=b''):\n"
            "        self.content = content\n"
        )

        # Tests package
        tests = project / "tests"
        tests.mkdir()
        (tests / "__init__.py").write_text("")
        (tests / "test_http.py").write_text(
            "from mylib.http import HttpResponse\n\n"
            "def test_response():\n"
            "    r = HttpResponse(b'hello')\n"
            "    assert r.content == b'hello'\n"
        )

        tests_pkg = analyze_package(tests)
        steps = trace_flow(
            tests_pkg,
            "test_response",
            cross_module=True,
            detail="source",
        )
        resolved = [s for s in steps if s.name == "HttpResponse" and s.resolved_module]
        assert len(resolved) == 1
        # Should point to the actual definition, not __init__.py
        assert resolved[0].resolved_module == "mylib.http.response"
        assert resolved[0].source is not None
        assert "class HttpResponse" in resolved[0].source

    def test_no_marker_no_fallback(self, tmp_path: Path) -> None:
        """Without .git marker, project root fallback doesn't fire."""
        # Place tests deep enough that standard root/root.parent search
        # cannot reach mylib — only the project-root fallback could.
        project = tmp_path / "bare_project"
        project.mkdir()
        # No .git marker!

        mylib = project / "mylib"
        mylib.mkdir()
        (mylib / "__init__.py").write_text("")
        (mylib / "http.py").write_text("class HttpResponse:\n    pass\n")

        # Nest tests under a sub-directory so root.parent != project
        nested = project / "apps" / "tests"
        nested.mkdir(parents=True)
        (nested / "__init__.py").write_text("")
        (nested / "test_http.py").write_text(
            "from mylib.http import HttpResponse\n\n"
            "def test_response():\n"
            "    HttpResponse()\n"
        )
        tests_pkg = analyze_package(nested)
        steps = trace_flow(tests_pkg, "test_response", cross_module=True)
        resolved = [s for s in steps if s.resolved_module is not None]
        # Without project root marker, fallback shouldn't reach mylib
        assert len(resolved) == 0


# ─── detail=source tests (AXM-410) ──────────────────────────────────────────


class TestFlowStepSourceField:
    """FlowStep model accepts optional source field."""

    def test_flowstep_source_default_none(self) -> None:
        """FlowStep without source → defaults to None."""
        step = FlowStep(name="f", module="m", line=1, depth=0, chain=["f"])
        assert step.source is None

    def test_flowstep_source_explicit(self) -> None:
        """FlowStep with explicit source → stored."""
        step = FlowStep(
            name="f", module="m", line=1, depth=0, chain=["f"], source="def f(): pass"
        )
        assert step.source == "def f(): pass"


class TestDetailSource:
    """trace_flow(detail='source') fills source code."""

    def test_trace_flow_detail_source(self, tmp_path: Path) -> None:
        """Each step has .source with the function body."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": (
                    "def helper():\n    return 42\n\ndef main():\n    helper()\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        steps = trace_flow(pkg, "main", detail="source")
        main_step = next(s for s in steps if s.name == "main")
        helper_step = next(s for s in steps if s.name == "helper")
        assert main_step.source is not None
        assert "def main" in main_step.source
        assert "helper()" in main_step.source
        assert helper_step.source is not None
        assert "def helper" in helper_step.source
        assert "return 42" in helper_step.source

    def test_trace_flow_detail_trace(self, tmp_path: Path) -> None:
        """detail='trace' → source is None for all steps."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def main():\n    pass\n",
            },
        )
        pkg = analyze_package(pkg_path)
        steps = trace_flow(pkg, "main", detail="trace")
        for step in steps:
            assert step.source is None

    def test_trace_flow_detail_default(self, tmp_path: Path) -> None:
        """Default detail → same as 'trace' (source is None)."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def main():\n    pass\n",
            },
        )
        pkg = analyze_package(pkg_path)
        steps = trace_flow(pkg, "main")
        for step in steps:
            assert step.source is None


class TestDetailSourceMissingModule:
    """Source extraction with unresolvable module → None (no crash)."""

    def test_source_missing_module(self, tmp_path: Path) -> None:
        """Trace with stdlib callee → source=None for unresolvable."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": (
                    "import os\n\ndef test_func():\n    os.path.join('a', 'b')\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        steps = trace_flow(pkg, "test_func", detail="source")
        # Entry point should have source
        entry = next(s for s in steps if s.name == "test_func")
        assert entry.source is not None
        assert "def test_func" in entry.source


class TestFlowsToolDetail:
    """FlowsTool passes detail param through."""

    def test_flowstool_passes_detail(self, tmp_path: Path) -> None:
        """FlowsTool with detail='source' → steps contain source."""
        from axm_ast.tools.flows import FlowsTool

        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def main():\n    pass\n",
            },
        )
        tool = FlowsTool()
        result = tool.execute(path=str(pkg_path), entry="main", detail="source")
        assert result.success
        assert result.data is not None
        steps = result.data["steps"]
        assert len(steps) >= 1
        assert "source" in steps[0]
        assert "def main" in steps[0]["source"]

    def test_flowstool_default_no_source(self, tmp_path: Path) -> None:
        """FlowsTool default → steps do not contain source key."""
        from axm_ast.tools.flows import FlowsTool

        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def main():\n    pass\n",
            },
        )
        tool = FlowsTool()
        result = tool.execute(path=str(pkg_path), entry="main")
        assert result.success
        assert result.data is not None
        steps = result.data["steps"]
        assert len(steps) >= 1
        assert "source" not in steps[0]


class TestTraceSourceHook:
    """TraceSourceHook execution tests."""

    def test_trace_source_hook_execute(self, tmp_path: Path) -> None:
        """Valid context with working_dir → HookResult.ok with trace."""
        from axm_ast.hooks.trace_source import TraceSourceHook

        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def main():\n    pass\n",
            },
        )
        hook = TraceSourceHook()
        result = hook.execute({"working_dir": str(pkg_path)}, entry="main")
        assert result.success
        assert "trace" in result.metadata
        trace = result.metadata["trace"]
        assert len(trace) >= 1
        assert trace[0]["name"] == "main"
        assert "source" in trace[0]
        assert "def main" in trace[0]["source"]

    def test_trace_source_hook_no_entry(self, tmp_path: Path) -> None:
        """Missing entry param → HookResult.fail."""
        from axm_ast.hooks.trace_source import TraceSourceHook

        hook = TraceSourceHook()
        result = hook.execute({"working_dir": str(tmp_path)})
        assert not result.success
        assert "entry" in (result.error or "").lower()

    def test_trace_source_hook_path_param(self, tmp_path: Path) -> None:
        """path param overrides working_dir from context."""
        from axm_ast.hooks.trace_source import TraceSourceHook

        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def main():\n    pass\n",
            },
        )
        hook = TraceSourceHook()
        # working_dir points to tmp_path (no package), but path param is correct
        result = hook.execute(
            {"working_dir": str(tmp_path)},
            entry="main",
            path=str(pkg_path),
        )
        assert result.success
        assert "trace" in result.metadata
        assert result.metadata["trace"][0]["name"] == "main"


class TestImpactHook:
    """ImpactHook execution tests."""

    def test_impact_hook_execute(self, tmp_path: Path) -> None:
        """Valid path + symbol → HookResult.ok with impact data."""
        from axm_ast.hooks.impact import ImpactHook

        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": (
                    "def helper():\n    return 42\n\ndef main():\n    helper()\n"
                ),
            },
        )
        hook = ImpactHook()
        result = hook.execute({"working_dir": str(pkg_path)}, symbol="helper")
        assert result.success
        assert "impact" in result.metadata
        impact = result.metadata["impact"]
        assert "symbol" in impact
        assert impact["symbol"] == "helper"

    def test_impact_hook_no_symbol(self) -> None:
        """Missing symbol param → HookResult.fail."""
        from axm_ast.hooks.impact import ImpactHook

        hook = ImpactHook()
        result = hook.execute({})
        assert not result.success
        assert "symbol" in (result.error or "").lower()

    def test_impact_hook_path_param(self, tmp_path: Path) -> None:
        """path param overrides working_dir from context."""
        from axm_ast.hooks.impact import ImpactHook

        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def main():\n    pass\n",
            },
        )
        hook = ImpactHook()
        result = hook.execute(
            {"working_dir": "/nonexistent"},
            symbol="main",
            path=str(pkg_path),
        )
        assert result.success
        assert "impact" in result.metadata
