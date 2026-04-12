"""AXM-AST CLI entry point — AST introspection for AI agents.

Usage::

    axm-ast describe src/mylib
    axm-ast describe src/mylib --detail detailed --json
    axm-ast inspect src/mylib --symbol MyClass
    axm-ast inspect src/mylib --symbol MyClass --source --json
    axm-ast graph src/mylib --format mermaid
    axm-ast search src/mylib --returns str
    axm-ast version
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Annotated, Any

import cyclopts

from axm_ast.core.analyzer import (
    search_symbols,
)
from axm_ast.core.cache import get_package
from axm_ast.formatters import (
    format_json,
    format_mermaid,
    format_text,
)
from axm_ast.models.nodes import SymbolKind

logger = logging.getLogger(__name__)

__all__ = ["app"]

app = cyclopts.App(
    name="axm-ast",
    help=(
        "AXM AST — Python library introspection for AI agents, powered by tree-sitter."
    ),
)


def _resolve_dir(path: str) -> Path:
    """Resolve *path* to an absolute directory, or exit with an error."""
    resolved = Path(path).resolve()
    if not resolved.is_dir():
        print(f"❌ Not a directory: {resolved}", file=sys.stderr)
        raise SystemExit(1)
    return resolved


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
            help="Detail level: summary, detailed",
        ),
    ] = "detailed",
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
    modules: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--modules", "-m"],
            help="Comma-separated module name filters (substring, case-insensitive)",
        ),
    ] = None,
) -> None:
    """Describe a Python package at the chosen detail level."""
    if detail == "full":
        print(
            "❌ detail='full' has been removed. "
            "Use --detail detailed or ast_inspect --source.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if compress and detail not in ("summary", "detailed"):
        print(
            f"❌ --compress and --detail {detail} are mutually exclusive. "
            "Use --compress alone or --detail without --compress.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    project_path = _resolve_dir(path)

    from axm_ast.formatters import filter_modules, format_toc

    pkg = get_package(project_path)

    # Apply module filter
    mod_filter = [m.strip() for m in modules.split(",")] if modules else None
    pkg = filter_modules(pkg, mod_filter)

    if detail == "toc":
        _print_toc(format_toc(pkg), json_output=json_output)
        return

    if compress:
        from axm_ast.formatters import format_compressed

        print(format_compressed(pkg))
    elif json_output:
        print(json.dumps(format_json(pkg, detail=detail), indent=2))
    else:
        print(format_text(pkg, detail=detail, budget=budget, rank=rank))


def _print_toc(toc: list[dict[str, object]], *, json_output: bool) -> None:
    """Print table-of-contents output."""
    if json_output:
        print(json.dumps({"modules": toc, "module_count": len(toc)}, indent=2))
    else:
        for entry in toc:
            sym = entry["symbol_count"]
            doc = f" — {entry['docstring']}" if entry["docstring"] else ""
            print(f"  {entry['name']} ({sym} symbols){doc}")


def _inspect_batch(
    project_path: Path, symbols: list[str], *, source: bool, json_output: bool
) -> None:
    """Handle --symbols batch inspection path."""
    from axm_ast.tools.inspect import InspectTool

    tool = InspectTool()
    result = tool.execute(path=str(project_path), symbols=symbols, source=source)

    if not result.success:
        print(f"❌ {result.error}", file=sys.stderr)
        raise SystemExit(1)

    if json_output:
        print(json.dumps(result.data, indent=2))
    else:
        print(result.text)


def _inspect_list_all(project_path: Path, *, json_output: bool) -> None:
    """List all symbols in a package."""
    pkg = get_package(project_path)
    all_symbols = search_symbols(pkg, name=None, returns=None, kind=None, inherits=None)
    if json_output:
        print(
            json.dumps(
                {"symbols": [s.model_dump(mode="json") for _, s in all_symbols]},
                indent=2,
            )
        )
    else:
        for _, s in all_symbols:
            sig = getattr(s, "signature", None)
            print(f"  · {sig}" if sig else f"  · class {s.name}")


@app.command()
def inspect(
    path: Annotated[
        str,
        cyclopts.Parameter(help="Path to package directory"),
    ] = ".",
    *,
    symbol: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--symbol", "-s"],
            help="Symbol name to inspect (supports dotted paths like Class.method)",
        ),
    ] = None,
    symbols: Annotated[
        list[str] | None,
        cyclopts.Parameter(
            name=["--symbols"],
            consume_multiple=True,
            help="Symbol names to inspect in batch",
        ),
    ] = None,
    source: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--source"],
            help="Include source code in output",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        cyclopts.Parameter(name=["--json"], help="Output as JSON"),
    ] = False,
) -> None:
    """Inspect a symbol by name across a package.

    Operates on packages (not individual files). Supports dotted paths
    like ``ClassName.method`` or ``module.symbol``. Returns file path,
    line numbers, and optionally source code — matching MCP ``ast_inspect``.
    """
    if symbol and symbols:
        print("❌ --symbol and --symbols are mutually exclusive", file=sys.stderr)
        raise SystemExit(1)

    project_path = _resolve_dir(path)

    if symbols:
        _inspect_batch(project_path, symbols, source=source, json_output=json_output)
        return

    if not symbol:
        _inspect_list_all(project_path, json_output=json_output)
        return

    from axm_ast.tools.inspect import InspectTool

    tool = InspectTool()
    result = tool.execute(path=str(project_path), symbol=symbol, source=source)

    if not result.success:
        print(f"❌ {result.error}", file=sys.stderr)
        raise SystemExit(1)

    if json_output:
        print(json.dumps(result.data["symbol"], indent=2))
    else:
        print(result.text)


def _print_graph_data(
    graph_data: dict[str, list[str]],
    label: str,
) -> None:
    """Print a graph adjacency list in text format."""
    if not graph_data:
        print(f"📊 No {label} detected")
    else:
        print(f"📊 {label}:")
        for src, targets in sorted(graph_data.items()):
            for t in targets:
                print(f"   {src} → {t}")


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
    project_path = _resolve_dir(path)

    from axm_ast.core.workspace import detect_workspace

    ws = detect_workspace(project_path)
    if ws is not None:
        _print_workspace_graph(project_path, fmt=fmt, json_output=json_output)
        return

    _print_package_graph(project_path, fmt=fmt, json_output=json_output)


def _print_workspace_graph(project_path: Path, *, fmt: str, json_output: bool) -> None:
    """Print a workspace-level dependency graph."""
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
        _print_graph_data(graph_data, "Workspace Package Graph")


def _print_package_graph(project_path: Path, *, fmt: str, json_output: bool) -> None:
    """Print a package-level import graph."""
    from axm_ast.core.analyzer import build_import_graph

    pkg = get_package(project_path)

    if json_output or fmt == "json":
        print(json.dumps(build_import_graph(pkg), indent=2))
    elif fmt == "mermaid":
        print(format_mermaid(pkg))
    else:
        _print_graph_data(build_import_graph(pkg), "Import Graph")


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
                "Filter by kind: function, method, property,"
                " classmethod, staticmethod, abstract, class"
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
    project_path = _resolve_dir(path)

    pkg = get_package(project_path)

    kind_enum = SymbolKind(kind) if kind else None
    results = search_symbols(
        pkg, name=name, returns=returns, kind=kind_enum, inherits=inherits
    )

    if not results:
        print("No results found.")
        return

    if json_output:
        print(json.dumps([r.model_dump(mode="json") for _, r in results], indent=2))
    else:
        print(f"🔍 {len(results)} result(s):\n")
        for _, r in results:
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
    project_path = _resolve_dir(path)

    from axm_ast.core.workspace import detect_workspace

    ws = detect_workspace(project_path)
    if ws is not None:
        from axm_ast.core.callers import find_callers_workspace
        from axm_ast.core.workspace import analyze_workspace

        ws = analyze_workspace(project_path)
        results = find_callers_workspace(ws, symbol)
    else:
        pkg = get_package(project_path)

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
def callees(
    path: Annotated[
        str,
        cyclopts.Parameter(help="Path to package directory"),
    ] = ".",
    *,
    symbol: Annotated[
        str,
        cyclopts.Parameter(
            name=["--symbol", "-s"],
            help="Symbol name to find callees of",
        ),
    ],
    json_output: Annotated[
        bool,
        cyclopts.Parameter(name=["--json"], help="Output as JSON"),
    ] = False,
) -> None:
    """Find all functions/methods called by a given symbol."""
    project_path = _resolve_dir(path)

    pkg = get_package(project_path)

    from axm_ast.core.flows import find_callees

    results = find_callees(pkg, symbol)

    if json_output:
        print(
            json.dumps(
                [r.model_dump(mode="json") for r in results],
                indent=2,
            )
        )
    elif not results:
        print(f"📭 No callees found for '{symbol}'")
    else:
        print(f"📞 {len(results)} callee(s) of '{symbol}':\n")
        for r in results:
            ctx = f" in {r.context}()" if r.context else ""
            print(f"  {r.module}:{r.line} → {r.symbol}{ctx}")
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
    depth: Annotated[
        int | None,
        cyclopts.Parameter(
            name=["--depth", "-d"],
            help="Detail level: 0=top-5, 1=sub-packages, 2=modules, 3=symbols",
        ),
    ] = None,
) -> None:
    """Dump complete project context in one shot for AI agents."""
    project_path = _resolve_dir(path)

    from axm_ast.core.workspace import detect_workspace

    ws = detect_workspace(project_path)
    if ws is not None:
        _print_workspace_context(project_path, json_output=json_output, depth=depth)
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
        print(json.dumps(format_context_json(ctx, depth=depth), indent=2))
    elif depth is not None:
        _print_compact_context(format_context_json(ctx, depth=depth))
    else:
        print(format_context(ctx))


def _print_workspace_context(
    project_path: Path, *, json_output: bool, depth: int | None = None
) -> None:
    """Print workspace-level context."""
    from axm_ast.core.workspace import (
        build_workspace_context,
        format_workspace_context,
    )

    ctx = build_workspace_context(project_path)
    ctx = format_workspace_context(ctx, depth=depth if depth is not None else 1)
    if json_output:
        print(json.dumps(ctx, indent=2))
        return
    print(f"🏗️  Workspace: {ctx['workspace']}")
    print(f"   Packages: {ctx['package_count']}")
    for pkg in ctx["packages"]:
        if "module_count" in pkg:
            print(
                f"   • {pkg['name']} "
                f"({pkg['module_count']} modules, "
                f"{pkg['function_count']} functions)"
            )
        else:
            print(f"   • {pkg['name']}")
    if ctx.get("package_graph"):
        print("\n📊 Package Dependencies:")
        for src, targets in sorted(ctx["package_graph"].items()):
            for t in targets:
                print(f"   {src} → {t}")


_DISPLAY_SYMS = 5


def _print_compact_context(data: dict[str, object]) -> None:
    """Print a compact context summary."""
    from typing import Any, cast

    d = cast(dict[str, Any], data)
    print(f"📋 {d['name']}")
    print(f"  python: {d['python']}")
    p = d["patterns"]
    print(
        f"  layout: {p['layout']}"
        f" ({p['module_count']} modules,"
        f" {p['function_count']} functions,"
        f" {p['class_count']} classes)"
    )
    top = d.get("top_modules")
    if top:
        print("\n📦 Top Modules")
        for m in top:
            stars = "★" * m["stars"] + "☆" * (5 - m["stars"])
            print(f"  {m['name']:30s} {stars}  ({m['symbol_count']} symbols)")
    packages = d.get("packages")
    if packages:
        print("\n📦 Packages")
        for name, info in packages.items():
            syms = info.get("symbol_names", [])
            sym_text = f" — {', '.join(syms[:_DISPLAY_SYMS])}" if syms else ""
            if len(syms) > _DISPLAY_SYMS:
                sym_text += f"... (+{len(syms) - _DISPLAY_SYMS})"
            mods = info["modules"]
            sym_count = info["symbols"]
            print(f"  {name:30s} {mods:>3d} modules, {sym_count:>4d} symbols{sym_text}")


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
    exclude_tests: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--exclude-tests"],
            help="Filter test callers from impact output",
        ),
    ] = False,
    test_filter: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--test-filter"],
            help="Test caller filter mode: none, all, or related",
        ),
    ] = None,
    compact: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--compact"],
            help="Output a compact markdown table summary",
        ),
    ] = False,
) -> None:
    """Analyze the impact of changing a symbol."""
    from axm_ast.tools.impact import ImpactTool

    detail = "compact" if compact else None
    tool = ImpactTool()
    tool_result = tool.execute(
        path=path,
        symbol=symbol,
        exclude_tests=exclude_tests,
        test_filter=test_filter,
        detail=detail,
    )

    if not tool_result.success:
        print(tool_result.error, file=sys.stderr)
        raise SystemExit(1)

    if compact:
        print(tool_result.data["compact"])
    elif json_output:
        print(json.dumps(tool_result.data, indent=2))
    else:
        _print_impact(tool_result.data)


def _print_impact(result: dict[str, Any]) -> None:
    """Pretty-print impact analysis."""
    sym = result["symbol"]
    score = result["score"]
    print(f"💥 Impact analysis for '{sym}' — {score}\n")

    defn = result.get("definition")
    if defn:
        print(f"  📍 Defined in: {defn['module']} (L{defn['line']})")
        print()

    _print_impact_callers(result.get("callers", []))
    _print_impact_type_refs(result.get("type_refs", []))
    _print_impact_list("📄 Affected modules", result.get("affected_modules", []))
    _print_impact_list("🧪 Tests to rerun", result.get("test_files", []))
    _print_impact_list("📦 Re-exported in", result.get("reexports", []))


def _print_impact_callers(callers: list[dict[str, Any]]) -> None:
    """Print callers section."""
    if not callers:
        return
    print(f"  📞 Direct callers ({len(callers)}):")
    for c in callers:
        ctx = f" in {c['context']}()" if c.get("context") else ""
        print(f"    {c['module']}:{c['line']}{ctx}")
    print()


def _print_impact_type_refs(
    type_refs: list[dict[str, Any]],
) -> None:
    """Print type references section."""
    if not type_refs:
        return
    print(f"  🔗 Type references ({len(type_refs)}):")
    for ref in type_refs:
        kind = ref.get("ref_type", "")
        print(f"    {ref['module']}:{ref['line']} {ref['function']} ({kind})")
    print()


def _print_impact_list(icon_label: str, items: list[str]) -> None:
    """Print a simple list section."""
    if not items:
        return
    print(f"  {icon_label} ({len(items)}):")
    for item in items:
        print(f"    {item}")
    print()


@app.command(name="diff")
def diff_cmd(
    refs: Annotated[
        str,
        cyclopts.Parameter(help="Git refs in base..head format"),
    ],
    path: Annotated[
        str,
        cyclopts.Parameter(help="Path to package directory"),
    ] = ".",
    *,
    json_output: Annotated[
        bool,
        cyclopts.Parameter(name=["--json"], help="Output as JSON"),
    ] = False,
) -> None:
    """Structural diff between two branches at symbol level."""
    if ".." not in refs:
        print("❌ Expected format: base..head (e.g. main..feature)", file=sys.stderr)
        raise SystemExit(1)

    parts = refs.split("..", 1)
    base, head = parts[0], parts[1]
    if not base or not head:
        print("❌ Both base and head refs are required", file=sys.stderr)
        raise SystemExit(1)

    project_path = _resolve_dir(path)

    from axm_ast.core.structural_diff import structural_diff

    result = structural_diff(project_path, base, head)

    if "error" in result:
        print(f"❌ {result['error']}", file=sys.stderr)
        raise SystemExit(1)

    if json_output:
        print(json.dumps(result, indent=2))
    else:
        _print_diff(result, base, head)


def _print_diff(result: dict[str, Any], base: str, head: str) -> None:
    """Pretty-print structural diff."""
    added = result["added"]
    removed = result["removed"]
    modified = result["modified"]
    summary = result["summary"]

    total = summary["added"] + summary["removed"] + summary["modified"]
    print(f"🔀 Structural diff {base}..{head} — {total} change(s)\n")

    if added:
        print(f"  Symbols added ({len(added)}):")
        for s in added:
            print(f"    + {s['name']} ({s['kind']}) — {s['file']}")
        print()

    if modified:
        print(f"  Symbols modified ({len(modified)}):")
        for s in modified:
            print(f"    ~ {s['name']} ({s['kind']}) — {s['file']}")
        print()

    if removed:
        print(f"  Symbols removed ({len(removed)}):")
        for s in removed:
            print(f"    - {s['name']} ({s['kind']}) — {s['file']}")
        print()

    if total == 0:
        print("  No structural changes detected.")


@app.command(name="dead-code")
def dead_code(
    path: Annotated[
        str,
        cyclopts.Parameter(help="Path to package directory"),
    ] = ".",
    *,
    json_output: Annotated[
        bool,
        cyclopts.Parameter(name=["--json"], help="Output as JSON"),
    ] = False,
    include_tests: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--include-tests"],
            help="Include test fixtures in scan",
        ),
    ] = False,
) -> None:
    """Detect dead (unreferenced) code in a Python package."""
    project_path = _resolve_dir(path)

    from axm_ast.core.dead_code import find_dead_code, format_dead_code

    pkg = get_package(project_path)
    results = find_dead_code(pkg, include_tests=include_tests)

    if json_output:
        print(
            json.dumps(
                {
                    "dead_symbols": [
                        {
                            "name": d.name,
                            "module_path": d.module_path,
                            "line": d.line,
                            "kind": d.kind,
                        }
                        for d in results
                    ],
                    "total": len(results),
                },
                indent=2,
            )
        )
    else:
        print(format_dead_code(results))


@app.command()
def flows(
    path: Annotated[
        str,
        cyclopts.Parameter(help="Path to package directory"),
    ] = ".",
    *,
    trace: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--trace", "-t"],
            help="Entry point name to trace flow from",
        ),
    ] = None,
    max_depth: Annotated[
        int,
        cyclopts.Parameter(
            name=["--max-depth"],
            help="Maximum BFS depth for flow tracing",
        ),
    ] = 5,
    cross_module: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--cross-module"],
            help="Resolve imports and trace into external modules",
        ),
    ] = False,
    detail: Annotated[
        str,
        cyclopts.Parameter(
            name=["--detail", "-d"],
            help="Detail level: trace (default) or source (include function source)",
        ),
    ] = "trace",
    no_exclude_stdlib: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--no-exclude-stdlib"],
            help="Include stdlib/builtin callees in flow trace",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        cyclopts.Parameter(name=["--json"], help="Output as JSON"),
    ] = False,
) -> None:
    """Detect entry points and trace execution flows."""
    project_path = _resolve_dir(path)

    from axm_ast.core.flows import (
        VALID_DETAILS,
        find_entry_points,
        format_flow_compact,
        format_flows,
        trace_flow,
    )

    if detail not in VALID_DETAILS:
        print(
            f"Invalid detail={detail!r}; must be one of {sorted(VALID_DETAILS)}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    pkg = get_package(project_path)

    if trace is not None:
        try:
            steps, _truncated = trace_flow(
                pkg,
                trace,
                max_depth=max_depth,
                cross_module=cross_module,
                detail=detail,
                exclude_stdlib=not no_exclude_stdlib,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1) from None
        if json_output:
            print(
                json.dumps(
                    {
                        "entry": trace,
                        "steps": [s.model_dump(mode="json") for s in steps],
                        "count": len(steps),
                    },
                    indent=2,
                )
            )
        elif not steps:
            print(f"📭 No flow found for '{trace}'")
        else:
            print(f"🔀 Flow from '{trace}' ({len(steps)} step(s)):\n")
            print(format_flow_compact(steps))
        return

    entries = find_entry_points(pkg)
    if json_output:
        print(
            json.dumps(
                {
                    "entry_points": [e.model_dump(mode="json") for e in entries],
                    "count": len(entries),
                },
                indent=2,
            )
        )
    else:
        print(format_flows(entries))


@app.command()
def docs(
    path: Annotated[
        str,
        cyclopts.Parameter(help="Project root directory"),
    ] = ".",
    *,
    detail: Annotated[
        str,
        cyclopts.Parameter(
            name=["--detail", "-d"],
            help="Detail level: toc, summary, full",
        ),
    ] = "full",
    pages_filter: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--pages", "-p"],
            help="Comma-separated page name substrings to filter",
        ),
    ] = None,
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
    project_path = _resolve_dir(path)

    from axm_ast.core.docs import discover_docs, format_docs, format_docs_json

    pages = [p.strip() for p in pages_filter.split(",")] if pages_filter else None
    result = discover_docs(project_path, detail=detail, pages=pages)

    if json_output:
        print(json.dumps(format_docs_json(result), indent=2))
    else:
        print(format_docs(result, tree_only=tree_only))


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
