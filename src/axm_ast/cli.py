"""AXM-AST CLI entry point — AST introspection for AI agents.

Usage::

    axm-ast describe src/mylib
    axm-ast describe src/mylib --detail detailed --json
    axm-ast inspect src/mylib/core.py --symbol MyClass
    axm-ast graph src/mylib --format mermaid
    axm-ast search src/mylib --returns str
    axm-ast stub src/mylib
    axm-ast version
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import cyclopts

from axm_ast.core.analyzer import (
    analyze_package,
    generate_stubs,
    search_symbols,
)
from axm_ast.core.parser import extract_module_info
from axm_ast.formatters import format_json, format_mermaid, format_text
from axm_ast.models.nodes import FunctionKind

__all__ = ["app"]

app = cyclopts.App(
    name="axm-ast",
    help=(
        "AXM AST — Python library introspection for AI agents, powered by tree-sitter."
    ),
)


@app.command()
def describe(
    path: Annotated[
        str,
        cyclopts.Parameter(help="Path to package/module directory"),
    ] = ".",
    *,
    detail: Annotated[
        str,
        cyclopts.Parameter(
            name=["--detail", "-d"],
            help="Detail level: summary, detailed, full",
        ),
    ] = "summary",
    json_output: Annotated[
        bool,
        cyclopts.Parameter(name=["--json"], help="Output as JSON"),
    ] = False,
    budget: Annotated[
        int | None,
        cyclopts.Parameter(
            name=["--budget", "-b"],
            help="Max output lines (truncate intelligently)",
        ),
    ] = None,
    rank: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--rank"],
            help="Sort symbols by importance (PageRank)",
        ),
    ] = False,
    compress: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--compress"],
            help="Compressed output: signatures + docstring summaries",
        ),
    ] = False,
) -> None:
    """Describe a Python package at the chosen detail level."""
    project_path = Path(path).resolve()
    if not project_path.is_dir():
        print(f"❌ Not a directory: {project_path}", file=sys.stderr)
        raise SystemExit(1)

    pkg = analyze_package(project_path)

    if compress:
        from axm_ast.formatters import format_compressed

        print(format_compressed(pkg))
    elif json_output:
        print(json.dumps(format_json(pkg, detail=detail), indent=2))
    else:
        print(format_text(pkg, detail=detail, budget=budget, rank=rank))


@app.command()
def inspect(
    path: Annotated[
        str,
        cyclopts.Parameter(help="Path to a Python file"),
    ],
    *,
    symbol: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--symbol", "-s"],
            help="Filter to a specific symbol name",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        cyclopts.Parameter(name=["--json"], help="Output as JSON"),
    ] = False,
) -> None:
    """Inspect a specific module or symbol."""
    file_path = Path(path).resolve()
    if not file_path.exists():
        print(f"❌ File not found: {file_path}", file=sys.stderr)
        raise SystemExit(1)

    # If path is a directory, inspect its __init__.py
    if file_path.is_dir():
        init = file_path / "__init__.py"
        if init.exists():
            file_path = init
        else:
            print(f"❌ No __init__.py in: {file_path}", file=sys.stderr)
            raise SystemExit(1)

    mod = extract_module_info(file_path)

    if symbol:
        _print_symbol(mod, symbol, json_output=json_output)
    else:
        _print_module(mod, json_output=json_output)


def _print_symbol(mod: object, name: str, *, json_output: bool) -> None:
    """Print information about a specific symbol."""
    from axm_ast.models.nodes import ModuleInfo

    assert isinstance(mod, ModuleInfo)

    for fn in mod.functions:
        if fn.name == name:
            _print_fn_detail(fn, json_output=json_output)
            return

    for cls in mod.classes:
        if cls.name == name:
            _print_cls_detail(cls, json_output=json_output)
            return

    print(f"❌ Symbol '{name}' not found", file=sys.stderr)
    raise SystemExit(1)


def _print_fn_detail(fn: object, *, json_output: bool) -> None:
    """Print detailed function info."""
    from axm_ast.models.nodes import FunctionInfo

    assert isinstance(fn, FunctionInfo)
    if json_output:
        print(json.dumps(fn.model_dump(mode="json"), indent=2))
    else:
        print(f"🔍 {fn.signature}")
        if fn.docstring:
            print(f"   {fn.docstring.strip()}")
        print(f"   kind: {fn.kind.value}")
        print(f"   lines: {fn.line_start}-{fn.line_end}")


def _print_cls_detail(cls: object, *, json_output: bool) -> None:
    """Print detailed class info."""
    from axm_ast.models.nodes import ClassInfo

    assert isinstance(cls, ClassInfo)
    if json_output:
        print(json.dumps(cls.model_dump(mode="json"), indent=2))
    else:
        bases = f"({', '.join(cls.bases)})" if cls.bases else ""
        print(f"🔍 class {cls.name}{bases}")
        if cls.docstring:
            print(f"   {cls.docstring.strip()}")
        for m in cls.methods:
            print(f"   · {m.signature}")


def _print_module(mod: object, *, json_output: bool) -> None:
    """Print full module information."""
    from axm_ast.models.nodes import ModuleInfo

    assert isinstance(mod, ModuleInfo)

    if json_output:
        print(json.dumps(mod.model_dump(mode="json"), indent=2))
        return

    print(f"📄 {mod.path.name}")
    if mod.docstring:
        first_line = mod.docstring.strip().split("\n")[0]
        print(f"   {first_line}")
    print()

    for fn in mod.functions:
        _print_fn_summary(fn)

    for cls in mod.classes:
        _print_cls_summary(cls)


def _print_fn_summary(fn: object) -> None:
    """Print a function summary line."""
    from axm_ast.models.nodes import FunctionInfo

    assert isinstance(fn, FunctionInfo)
    pub = "🔓" if fn.is_public else "🔒"
    print(f"  {pub} {fn.signature}")
    if fn.docstring:
        first_line = fn.docstring.strip().split("\n")[0]
        print(f"     {first_line}")


def _print_cls_summary(cls: object) -> None:
    """Print a class summary line."""
    from axm_ast.models.nodes import ClassInfo

    assert isinstance(cls, ClassInfo)
    pub = "🔓" if cls.is_public else "🔒"
    bases = f"({', '.join(cls.bases)})" if cls.bases else ""
    print(f"  {pub} class {cls.name}{bases}")
    for m in cls.methods:
        print(f"     · {m.signature}")


@app.command()
def graph(
    path: Annotated[
        str,
        cyclopts.Parameter(help="Path to package or workspace directory"),
    ] = ".",
    *,
    fmt: Annotated[
        str,
        cyclopts.Parameter(
            name=["--format", "-f"],
            help="Output format: text, mermaid, json",
        ),
    ] = "text",
    json_output: Annotated[
        bool,
        cyclopts.Parameter(name=["--json"], help="Output as JSON"),
    ] = False,
) -> None:
    """Display the internal import/dependency graph."""
    project_path = Path(path).resolve()
    if not project_path.is_dir():
        print(f"❌ Not a directory: {project_path}", file=sys.stderr)
        raise SystemExit(1)

    from axm_ast.core.workspace import detect_workspace

    ws = detect_workspace(project_path)
    if ws is not None:
        from axm_ast.core.workspace import (
            analyze_workspace,
            build_workspace_dep_graph,
            format_workspace_graph_mermaid,
        )

        ws = analyze_workspace(project_path)
        graph_data = build_workspace_dep_graph(ws)

        if json_output or fmt == "json":
            print(json.dumps(graph_data, indent=2))
        elif fmt == "mermaid":
            print(format_workspace_graph_mermaid(ws))
        else:
            if not graph_data:
                print("📊 No inter-package dependencies detected")
            else:
                print("📊 Workspace Package Graph:")
                for src, targets in sorted(graph_data.items()):
                    for t in targets:
                        print(f"   {src} → {t}")
        return

    pkg = analyze_package(project_path)

    if json_output or fmt == "json":
        from axm_ast.core.analyzer import build_import_graph

        print(json.dumps(build_import_graph(pkg), indent=2))
    elif fmt == "mermaid":
        print(format_mermaid(pkg))
    else:
        # Text format: simple adjacency list
        from axm_ast.core.analyzer import build_import_graph

        graph_data = build_import_graph(pkg)
        if not graph_data:
            print("📊 No internal imports detected")
        else:
            print("📊 Import Graph:")
            for src, targets in sorted(graph_data.items()):
                for t in targets:
                    print(f"   {src} → {t}")


@app.command()
def search(
    path: Annotated[
        str,
        cyclopts.Parameter(help="Path to package directory"),
    ] = ".",
    *,
    name: Annotated[
        str | None,
        cyclopts.Parameter(name=["--name", "-n"], help="Search by symbol name"),
    ] = None,
    returns: Annotated[
        str | None,
        cyclopts.Parameter(name=["--returns", "-r"], help="Filter by return type"),
    ] = None,
    kind: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--kind", "-k"],
            help=(
                "Filter by kind: function, method, property, classmethod, staticmethod"
            ),
        ),
    ] = None,
    inherits: Annotated[
        str | None,
        cyclopts.Parameter(name=["--inherits"], help="Filter classes by base class"),
    ] = None,
    json_output: Annotated[
        bool,
        cyclopts.Parameter(name=["--json"], help="Output as JSON"),
    ] = False,
) -> None:
    """Search for symbols across a package with filters."""
    project_path = Path(path).resolve()
    if not project_path.is_dir():
        print(f"❌ Not a directory: {project_path}", file=sys.stderr)
        raise SystemExit(1)

    pkg = analyze_package(project_path)

    kind_enum = FunctionKind(kind) if kind else None
    results = search_symbols(
        pkg, name=name, returns=returns, kind=kind_enum, inherits=inherits
    )

    if not results:
        print("No results found.")
        return

    if json_output:
        print(json.dumps([r.model_dump(mode="json") for r in results], indent=2))
    else:
        print(f"🔍 {len(results)} result(s):\n")
        for r in results:
            if hasattr(r, "signature"):
                print(f"  · {r.signature}")
            else:
                print(f"  · class {r.name}")


@app.command()
def callers(
    path: Annotated[
        str,
        cyclopts.Parameter(help="Path to package or workspace directory"),
    ] = ".",
    *,
    symbol: Annotated[
        str,
        cyclopts.Parameter(
            name=["--symbol", "-s"],
            help="Symbol name to search for callers of",
        ),
    ],
    json_output: Annotated[
        bool,
        cyclopts.Parameter(name=["--json"], help="Output as JSON"),
    ] = False,
) -> None:
    """Find all call-sites of a given symbol across a package."""
    project_path = Path(path).resolve()
    if not project_path.is_dir():
        print(f"❌ Not a directory: {project_path}", file=sys.stderr)
        raise SystemExit(1)

    from axm_ast.core.workspace import detect_workspace

    ws = detect_workspace(project_path)
    if ws is not None:
        from axm_ast.core.callers import find_callers_workspace
        from axm_ast.core.workspace import analyze_workspace

        ws = analyze_workspace(project_path)
        results = find_callers_workspace(ws, symbol)
    else:
        pkg = analyze_package(project_path)

        from axm_ast.core.callers import find_callers

        results = find_callers(pkg, symbol)

    if json_output:
        print(
            json.dumps(
                [r.model_dump(mode="json") for r in results],
                indent=2,
            )
        )
    elif not results:
        print(f"📭 No callers found for '{symbol}'")
    else:
        print(f"📞 {len(results)} caller(s) of '{symbol}':\n")
        for r in results:
            ctx = f" in {r.context}()" if r.context else ""
            print(f"  {r.module}:{r.line}{ctx}")
            print(f"    {r.call_expression}")


@app.command()
def context(
    path: Annotated[
        str,
        cyclopts.Parameter(help="Path to package or workspace directory"),
    ] = ".",
    *,
    json_output: Annotated[
        bool,
        cyclopts.Parameter(name=["--json"], help="Output as JSON"),
    ] = False,
) -> None:
    """Dump complete project context in one shot for AI agents."""
    project_path = Path(path).resolve()
    if not project_path.is_dir():
        print(f"❌ Not a directory: {project_path}", file=sys.stderr)
        raise SystemExit(1)

    from axm_ast.core.workspace import detect_workspace

    ws = detect_workspace(project_path)
    if ws is not None:
        from axm_ast.core.workspace import build_workspace_context

        ctx = build_workspace_context(project_path)
        if json_output:
            print(json.dumps(ctx, indent=2))
        else:
            print(f"🏗️  Workspace: {ctx['workspace']}")
            print(f"   Packages: {ctx['package_count']}")
            for pkg in ctx["packages"]:
                print(
                    f"   • {pkg['name']} "
                    f"({pkg['module_count']} modules, "
                    f"{pkg['function_count']} functions)"
                )
            if ctx["package_graph"]:
                print("\n📊 Package Dependencies:")
                for src, targets in sorted(ctx["package_graph"].items()):
                    for t in targets:
                        print(f"   {src} → {t}")
        return

    from axm_ast.core.context import (
        build_context as _build_context,
    )
    from axm_ast.core.context import (
        format_context,
        format_context_json,
    )

    ctx = _build_context(project_path)

    if json_output:
        print(json.dumps(format_context_json(ctx), indent=2))
    else:
        print(format_context(ctx))


@app.command()
def impact(
    path: Annotated[
        str,
        cyclopts.Parameter(help="Path to package or workspace directory"),
    ] = ".",
    *,
    symbol: Annotated[
        str,
        cyclopts.Parameter(
            name=["--symbol", "-s"],
            help="Symbol name to analyze impact for",
        ),
    ],
    json_output: Annotated[
        bool,
        cyclopts.Parameter(name=["--json"], help="Output as JSON"),
    ] = False,
) -> None:
    """Analyze the impact of changing a symbol."""
    project_path = Path(path).resolve()
    if not project_path.is_dir():
        print(f"❌ Not a directory: {project_path}", file=sys.stderr)
        raise SystemExit(1)

    from axm_ast.core.workspace import detect_workspace

    ws = detect_workspace(project_path)
    if ws is not None:
        from axm_ast.core.impact import analyze_impact_workspace

        result = analyze_impact_workspace(project_path, symbol)
    else:
        from axm_ast.core.impact import analyze_impact

        result = analyze_impact(project_path, symbol)

    if json_output:
        print(json.dumps(result, indent=2))
    else:
        _print_impact(result)


def _print_impact(result: dict) -> None:  # type: ignore[type-arg]
    """Pretty-print impact analysis."""
    sym = result["symbol"]
    score = result["score"]
    print(f"💥 Impact analysis for '{sym}' — {score}\n")

    defn = result.get("definition")
    if defn:
        print(f"  📍 Defined in: {defn['module']} (L{defn['line']})")
        print()

    _print_impact_callers(result.get("callers", []))
    _print_impact_list("📄 Affected modules", result.get("affected_modules", []))
    _print_impact_list("🧪 Tests to rerun", result.get("test_files", []))
    _print_impact_list("📦 Re-exported in", result.get("reexports", []))


def _print_impact_callers(callers: list[dict]) -> None:  # type: ignore[type-arg]
    """Print callers section."""
    if not callers:
        return
    print(f"  📞 Direct callers ({len(callers)}):")
    for c in callers:
        ctx = f" in {c['context']}()" if c.get("context") else ""
        print(f"    {c['module']}:{c['line']}{ctx}")
    print()


def _print_impact_list(icon_label: str, items: list[str]) -> None:
    """Print a simple list section."""
    if not items:
        return
    print(f"  {icon_label} ({len(items)}):")
    for item in items:
        print(f"    {item}")
    print()


@app.command()
def docs(
    path: Annotated[
        str,
        cyclopts.Parameter(help="Project root directory"),
    ] = ".",
    *,
    json_output: Annotated[
        bool,
        cyclopts.Parameter(name=["--json"], help="Output as JSON"),
    ] = False,
    tree_only: Annotated[
        bool,
        cyclopts.Parameter(name=["--tree"], help="Only show directory tree"),
    ] = False,
) -> None:
    """Dump project documentation tree and content in one shot."""
    project_path = Path(path).resolve()
    if not project_path.is_dir():
        print(f"❌ Not a directory: {project_path}", file=sys.stderr)
        raise SystemExit(1)

    from axm_ast.core.docs import discover_docs, format_docs, format_docs_json

    result = discover_docs(project_path)

    if json_output:
        print(json.dumps(format_docs_json(result), indent=2))
    else:
        print(format_docs(result, tree_only=tree_only))


@app.command()
def stub(
    path: Annotated[
        str,
        cyclopts.Parameter(help="Path to package directory"),
    ] = ".",
) -> None:
    """Generate compact .pyi-like stubs for AI consumption."""
    project_path = Path(path).resolve()
    if not project_path.is_dir():
        print(f"❌ Not a directory: {project_path}", file=sys.stderr)
        raise SystemExit(1)

    pkg = analyze_package(project_path)
    print(generate_stubs(pkg))


@app.command()
def version() -> None:
    """Show axm-ast version."""
    from axm_ast import __version__

    print(f"axm-ast {__version__}")


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
