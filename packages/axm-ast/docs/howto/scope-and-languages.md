# Choose scope and language

## Python packages

Pass a project directory or its import-package directory. For a project with
`src/<name>/__init__.py`, `analyze_package` selects that import package.
If several such directories exist, it selects the alphabetically first and logs
a warning; pass each import-package directory explicitly to cover the others.
A package analysis is not an implicit union of workspace members.

Discovery prunes virtual environments, caches and other non-source directories.
This is static parsing, not execution of the target package. Broken syntax can
yield partial tree-sitter results; extraction does not certify valid Python.

## uv workspaces

Use a uv workspace root for `context`, `callers`, `impact` and `graph`.
The AXM tool `ast_callees` also aggregates members, while the dedicated
`axm-ast callees` command analyzes one package.

| Graph scope | Result |
|---|---|
| Omitted on a package | Module import graph |
| Omitted on a workspace / `workspace-deps` | Inter-package dependency graph |
| `workspace` | Merged module graph, nodes named `{package}.{module}` |
| `package` | Force one-package analysis |

```bash
axm-ast graph . --scope workspace --format mermaid
axm-ast context packages/axm-ast --depth 1
```

Run these from a uv workspace root. Workspace call-site module names use
`package::module`, distinct from merged graph node names. Other tools do not
inherit workspace semantics merely because they accept `path`.

## TypeScript and TSX

```bash
uv add 'axm-ast[typescript]'
axm-ast describe /path/to/node-project --detail summary
axm-ast graph /path/to/node-project --format json
```

The Node path is selected only when the supplied directory contains
`package.json` and has neither a top-level `__init__.py` nor a Python package
under `src/`. Pass the Node project root, not its `src/` subdirectory.

The current discovery and backend registry accept **`.ts` and `.tsx` only**.
They do not discover `.js`, `.jsx`, or `.svelte`. A `.svelte.ts` file is
discovered as TypeScript; this does not parse a Svelte component. The backend
uses the TypeScript grammar for both suffixes, so TSX discovery does not imply
complete JSX grammar support.

It extracts named functions, arrow-function declarations, class methods,
interfaces, type aliases, enums and ES imports into shared models. Parameter,
inheritance and export metadata are less complete than Python extraction.
Do not interpret absent metadata as proof that the source lacks it.

Relative imports are resolved to local TypeScript files or directory indexes.
Bare npm imports, unresolved aliases and `tsconfig` path mappings are not
internal dependency edges. Python-specific flows, dead-code exemptions and
impact heuristics are not a complete TypeScript semantic analysis.

## Cache and freshness

The internal `axm_ast.core.cache.get_package(Path(...))` cache keys results by
resolved path and compares Python file paths plus nanosecond mtimes.
It does not fingerprint TypeScript files or configuration changes.
For changing Node sources, use separate CLI processes or explicitly call
`clear_cache()` in a Python integration before parsing again.
Even Python content changes with preserved mtimes can evade invalidation.

## Read-only boundaries

Source files are never refactored by these tools; use axm-anvil for mutations.
Impact can read git history. Structural diff creates temporary worktrees and
cleans them after comparing refs, so it requires git metadata writes even though
the analyzed source stays unchanged. Static call matching, one-hop external
flow resolution and lexical documentation impact all have limits:
[impact](impact.md), [cross-module resolution](../explanation/cross_module_resolution.md),
[documentation impact](../explanation/doc_impact_limits.md).
