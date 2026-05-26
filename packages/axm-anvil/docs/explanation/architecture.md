# Architecture

## Overview

`axm-anvil` follows a layered architecture with clear separation of concerns:

```mermaid
graph TD
    subgraph "User Interface"
        CLI["CLI"]
    end

    subgraph "Core Logic"
        Core["Business Logic"]
    end

    subgraph "Adapters"
        Ext["External Services"]
    end

    CLI --> Core
    Core --> Ext
```

## Layers

### 1. CLI

Entry point for user commands. Handles input validation and formatted output.

### 2. Core Logic (`core/`)

Business logic independent of I/O.

### 3. Adapters (`adapters/`)

Each adapter wraps a single external dependency for testability.

## Internal CST primitives (`_cst/`)

The private `axm_anvil._cst` sub-package groups libcst helpers shared by
the move/rename/split tooling. It is intentionally internal — consumers
should use the public `axm_anvil` API.

| Module | Responsibility |
|---|---|
| `_cst.blocks` | Extract top-level symbol `Block` records (node + leading lines + referenced names) |
| `_cst.visitors` | `_ReferenceCollector` (collect referenced root names) and `_dotted_name` (flatten `Attribute` chains) |
| `_cst.transformers` | `_RemoveSymbols` transformer that deletes targeted top-level `ClassDef`, `FunctionDef`, and constant (`Assign` / `AnnAssign`) nodes while preserving surrounding formatting; `_AttributeRewriter` rewrites `old_module.Symbol` attribute chains (and alias-bound equivalents) to `new_module.Symbol`, using `ScopeProvider` to skip shadowed names and tracking residual `old_module.*` references so the caller layer knows when it can drop the bare `import old_module` line |
| `_cst.overloads` | `_detect_overload_group` — find the ordered `@overload` companions of a symbol, with alias-aware detection. Delegates alias discovery to `_collect_overload_aliases`, which composes two small helpers: `_iter_typing_import_names` (walk `from typing import ...` lines) and `_overload_alias_name` (resolve one `ImportAlias` to the local name bound to `typing.overload`, or `None`) |

## Transitive dependency collection in `core.move`

When `move_symbols` relocates a block, it must also carry along the
helpers and constants that block references (and those they transitively
reference). The BFS traversal in `core/move.py` shares a small enqueue
step so callers stay focused on the walk itself:

| Helper | Responsibility |
|---|---|
| `_collect_transitive_deps` | BFS transitive closure over helpers and constants from block refs, stable on cycles |
| `_BfsState` | Dataclass bundling the mutable BFS state (source/collected helpers and constants, `seen`, `queue`) |
| `_visit_dep_name` | Resolve one dequeued name: record it as helper/constant and enqueue its refs |
| `_expand_refs_one_level` | Append unseen refs to the work queue, marking them in `seen` in place |

## Orphan detection in `core.move`

When `move_symbols` copies helpers and constants to a target module, some
of them may no longer be referenced by anything staying in the source. The
orphan-detection pipeline in `core/move.py` is split into three private
helpers to keep each piece small:

| Helper | Responsibility |
|---|---|
| `_compute_source_orphans` | Top-level entry; intersects candidates with actual source names and delegates |
| `_collect_top_level_refs` | Walks the module body to build `(all_top_names, refs_of)` |
| `_filter_still_referenced` | Iterates to stability, promoting candidates reachable from staying names |

## Caller rewriting in `core.callers`

When `move_symbols` relocates a symbol, every other file in the workspace
that imports it via `from old_module import Symbol` must be redirected to
the new module. The `core/callers.py` module isolates this concern behind
a small set of helpers so the main `move.py` pipeline stays focused on
source/target rendering:

| Helper | Responsibility |
|---|---|
| `_module_path_from_file` | Derive a dotted module path from a file path under a workspace root (strips `src/`, drops `.py`) |
| `_discover_callers` | Scan workspace `.py` files for `from <from_module> import` lines that reference any moved name |
| `_discover_module_import_callers` | Scan workspace `.py` files for bare `import old_module` (with optional `as` alias) statements that refer to the source module |
| `_rewrite_caller_text` | Rewrite a caller's text via libcst: remove moved names from the old import, add them to the new import, preserve asnames |
| `_add_new_imports` | Build a `CodemodContext` with `AddImportsVisitor.add_needed_import` calls for each matched moved name, preserving asnames |
| `_format_new_import_stmt` | Render the `from new_module import …` statement (with `as` aliases) used as the `new` side of the `CallerRewrite` record |
| `_rewrite_module_import_caller` | Rewrite `old_module.Symbol` attribute chains to `new_module.Symbol` via `_AttributeRewriter`, add `import new_module`, and drop `import old_module` when it has no residual uses |
| `CallerRewrite` | Per-line record `(file, line, old, new)` surfaced through `MovePlan.callers_updated` |

The `_process_callers` helper in `core/move.py` orchestrates the flow:
discover candidate callers (both `from`-imports and bare module imports),
parse + rewrite each via libcst, re-parse the result as a validation
gate, and stage the `(original, new)` text pairs for atomic write
alongside the source/target diffs through `batch_edit`. A caller that
uses *both* import styles is rewritten in a single pass so the final
text is validated once. The orchestrator delegates to three private
helpers to keep each piece small:

| Helper | Responsibility |
|---|---|
| `_dedup_caller_paths` | Merge `from`-import and module-import caller lists, preserving order while removing duplicates by resolved path |
| `_rewrite_one_caller` | Apply both rewrite passes to a single caller, validate via `cst.parse_module`, and return `None` when the file is unchanged |
| `_caller_relpath` | Render a caller path relative to the workspace root, falling back to the absolute path when outside the root |

## Implied target imports in `core.move`

When a moved block references names that are defined elsewhere in the
workspace, the target module needs a matching `import` so the block stays
valid in its new home. `_block_implied_target_imports` resolves each
referenced name to the module that will own it after the move:

| Helper | Responsibility |
|---|---|
| `_block_implied_target_imports` | Top-level entry; collects refs from moved blocks, dispatches each to the resolvers, and returns the set of internal modules the target should import |
| `_resolve_import_ref` | Resolve a ref via a source-side absolute import (skipping relative imports and refs that already resolve to the target) by walking dotted prefixes through `_resolve_internal_module` |
| `_resolve_symbol_ref` | Resolve a ref to `source_module` when it remains a top-level symbol staying behind in source |
| `_resolve_internal_module` | Resolve a dotted module name (or a parent prefix) to a known internal module |
| `_gather_source_imports` (in `core.deps`) | Map local names in the source module to the `ImportInfo` describing their origin |

Before adding any new import to the target tree, `_apply_imports`
consults `_gather_target_imports` (in `core.deps`) — the target-side
mirror of `_gather_source_imports` — to skip names already in scope.
This avoids `F811` redefinitions when the target file already imports a
name the moved block also references. When the existing target import
points at a different module than the source's import, the name is
still skipped but a `redundant import: …` warning is emitted into
`MovePlan.warnings` so the operator can reconcile the divergence.

## Re-export mode in `core.move`

When `move_symbols` is called with `reexport=True`, the pipeline skips
caller discovery entirely and instead appends
`from new_module import <Symbol>  # re-export for backwards compat` to
the source module after the removed symbol's slot. The new source text
is parse-validated alongside the target, then emitted in a single
`batch_edit` call containing exactly two replace operations (source +
target) and zero caller ops. `data["reexport"] = True` is surfaced for
observability and `_format_text` prints `Mode: reexport`. `reexport=True`
is incompatible with `rename=` and raises `ValueError` before any I/O.

## Import-cycle detection in `core.cycles`

Moving a symbol can introduce an import cycle when the target module
already depends on the source (directly or transitively), or when the
caller-rewrite step redirects an import in a way that closes a loop.
`core/cycles.py` isolates the graph-level reasoning so `core/move.py`
only has to assemble the edit set:

| Helper | Responsibility |
|---|---|
| `GraphEdits` | Dataclass bundling edge `adds` and `removes` to apply on an import graph |
| `detect_new_cycle` | Copy the current graph, apply `GraphEdits`, and return the first *newly introduced* cycle (ignoring pre-existing cycles) |
| `_TarjanState` | Dataclass holding Tarjan's mutable bookkeeping (indices, lowlinks, stacks, emitted SCCs) so step helpers can share it without long parameter lists |
| `_tarjan_sccs` | Iterative Tarjan SCC driver (no recursion, safe on large packages); delegates per-frame work to `_tarjan_step_descend` and `_tarjan_step_finalize` |
| `_cycles` | Filter SCCs to size > 1 plus genuine self-loops |
| `_order_cycle` | Order nodes along a directed walk for readable `A → B → C → A` output |

The `_cycle_check` helper in `core/move.py` builds the current
package-level module graph by parsing every `.py` file under the
detected package root, computes `GraphEdits` for the move (imports
dropped from the source, imports gained by the target, caller
redirections), and calls `detect_new_cycle`. A non-`None` result raises
`ImportCycleError` with the ordered cycle when `check=True` or during a
normal (non-dry-run) write; pure `dry_run=True` calls skip the raise to
preserve the existing preview contract.

## Design Decisions

| Decision | Rationale |
|---|---|
| Hexagonal architecture | Testable core, swappable adapters |
| Pydantic models | Validation, serialization |
| `src/` layout | PEP 621 best practice, no import conflicts |
| Private `_cst/` sub-package | Share libcst primitives across tools without leaking internals |
