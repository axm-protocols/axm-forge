# Python API guide

The stable package-root surface is exported through `axm_ast.__all__`.
Internal `axm_ast.core.*`, `formatters` and `tools.*` modules remain
importable but have a different stability boundary. Generated reference is
available in **Python API** in the navigation, including those implementation
modules; a generated listing alone is not a usage guide.

## Root re-exports

| Export | Use and result |
|---|---|
| `analyze_package(Path)` | Parse one directory into `PackageInfo`; invalid directory raises `ValueError` |
| `search_symbols(pkg, *, name=None, returns=None, kind=None, inherits=None)` | AND-combined filters; returns `(module_name, symbol)` tuples |
| `find_callers(pkg, symbol)` | Syntactic call sites as `list[CallSite]` |
| `trace_flow(pkg, entry, ...)` | Returns `(list[FlowStep], truncated)`, not just steps |
| `find_dead_code(pkg, *, include_tests=False)` | Returns `list[DeadSymbol]` candidates |
| `analyze_workspace(Path)` | Parse uv workspace members into `WorkspaceInfo` |
| `build_workspace_module_graph(ws)` | Merged adjacency mapping |
| `structural_diff(pkg_path, base, head)` | `StructuralDiffResult` dictionary; check its `error` key |
| `__version__` | Installed package version |

The root also exports `FunctionInfo`, `FunctionKind`, `ClassInfo`,
`VariableInfo`, `ParameterInfo`, `ImportInfo`, `ModuleInfo`,
`PackageInfo`, `WorkspaceInfo`, `CallSite`, `FlowStep`, and
`DeadSymbol`. These model objects support Pydantic serialization such as
`model_dump(mode="json")`. `StructuralDiffResult` is a TypedDict, not a
Pydantic model.

## Search and inspect parsed symbols

Run from an axm-forge checkout:

```python
from pathlib import Path
from axm_ast import FunctionInfo, analyze_package, search_symbols

pkg = analyze_package(Path("packages/axm-ast"))
for module, symbol in search_symbols(pkg, name="analyze_package"):
    if isinstance(symbol, FunctionInfo):
        print(module, symbol.name, symbol.signature)
```

Filters are lexical (name, annotation and base-class strings), not type
inference. No matches produces an empty list. Fuzzy suggestions belong to the
`ast_search` tool, not this function.

## Trace a call graph

```python
from pathlib import Path
from axm_ast import analyze_package, trace_flow

pkg = analyze_package(Path("packages/axm-ast"))
steps, truncated = trace_flow(pkg, "analyze_package", max_depth=1)
for step in steps:
    print(step.depth, step.name, step.module, step.line)
print("Depth limited:", truncated)
```

The root is depth zero. `detail="source"` enriches steps with function source;
`trace_flow` always returns the tuple even for `detail="compact"`.
The tool/CLI renders the compact tree. Invalid detail or missing entry raises
`ValueError`. Cross-module callees are recorded as single-hop leaves, not
recursively expanded.

## Workspace analysis

```python
from pathlib import Path
from axm_ast import analyze_workspace, build_workspace_module_graph

workspace = analyze_workspace(Path("."))
graph = build_workspace_module_graph(workspace)
for module, dependencies in graph.items():
    print(module, dependencies)
```

This example requires a uv workspace root. Use one member directory for
single-package APIs. [Scope and language limits](../howto/scope-and-languages.md)
cover src-layout selection and optional TypeScript support.

## Dead code and structural changes

`find_dead_code` uses name-based references and exemptions. Homonymous live
symbols can hide dead ones; dynamic consumers can also escape static matching.
Review findings before deleting code.

`structural_diff` compares symbols and signatures between git refs, with
temporary worktrees. A function-body-only change with an unchanged signature
does not appear as a modified symbol. It does not represent uncommitted changes.
Check `"error" in result` before reading `added`, `removed`, `modified`
or `summary`. This operation has git metadata side effects despite preserving
the source checkout.

## Internal helpers

These compatibility anchors preserve older links. Their current signatures are
generated from source below; integrations should prefer the root surface or
[AXM tools](tools.md).

### `format_context_json`
::: axm_ast.core.context.format_context_json

### `format_context_text`
::: axm_ast.core.context.format_context_text

### `build_workspace_context`
::: axm_ast.core.workspace.build_workspace_context

### `format_workspace_context`
::: axm_ast.core.workspace.format_workspace_context

### `search_symbols`
::: axm_ast.search_symbols

### `format_workspace_text`
::: axm_ast.core.workspace.format_workspace_text

### `score_impact`
::: axm_ast.core.impact.score_impact

### `format_impact_compact`
::: axm_ast.tools.impact.format_impact_compact

### `render_impact_text`
::: axm_ast.tools.impact_text.render_impact_text

### `FlowsTool.execute`
::: axm_ast.tools.flows.FlowsTool.execute

### `render_impact_batch_text`
::: axm_ast.tools.impact_text.render_impact_batch_text

### `ImpactTool.execute`
::: axm_ast.tools.impact.ImpactTool.execute
