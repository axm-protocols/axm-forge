# axm-anvil

**Deterministic CST-based refactoring toolkit for Python.**

<p align="center">
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-draft-workspace/gh-pages/badges/axm-anvil/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-draft-workspace/gh-pages/badges/axm-anvil/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-draft-workspace/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-draft-workspace/gh-pages/badges/axm-anvil/coverage.json" alt="Coverage"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
</p>

---

## Overview

Moving symbols (classes, functions, constants) between Python files is error-prone
when done by hand or via LLM text generation. `axm-anvil` replaces those rewrites
with **deterministic, CST-based transformations** that preserve formatting,
comments, and semantics exactly.

Built on [libcst](https://github.com/Instagram/LibCST) for lossless round-trip,
it exposes a set of MCP tools for agent-driven refactoring.

## Features

- 🔨 **`ast_move`** — Move classes, functions, or constants between files with transitive dependency resolution (imports, constants, helpers)
- 🔁 **Smart import merging** — Uses `AddImportsVisitor` to combine imports from the same module instead of duplicating
- 🧹 **Scope-aware orphan cleanup** — Source file's unused imports are removed via `ruff check --select F401 --fix`
- 📐 **Topological constant ordering** — Dependencies are always inserted before their dependents
- 🛡️ **Atomic writes** — All modifications computed in memory, validated via `cst.parse_module()`, then applied via a single `batch_edit` call (all-or-nothing)
- 🔗 **Attribute-style caller rewrites** — Rewrites `old_module.Symbol` chains (including `import ... as` aliases) to the new module, preserving method/subscript chains and skipping shadowed names via `ScopeProvider`
- 🪢 **`--reexport` mode** — Leaves callers untouched and injects a `from new_module import <Symbol>  # re-export for backwards compat` shim into the source module for gradual migration
- 🎯 **Overload-aware** — Detects `@overload` companions and moves them together as an indivisible group
- 📦 **Lossless formatting** — Comments, whitespace, and trailing commas preserved exactly via libcst round-trip
- 🤝 **Complementary to `axm-ast`** — Uses `ast_callers` and `ast_graph` for blast radius detection

### Planned tools (see `spec.md`)

| Tool | Description |
|---|---|
| `ast_move` | Move symbols between files (Phase 1-3) |
| `ast_rename` | Rename a symbol everywhere (def + callers + imports + `__all__`) |
| `ast_split` | Split a module into N sub-modules |
| `ast_merge` | Merge N modules into one |
| `ast_promote` | `_foo` → `foo` + add `__all__` + update imports |
| `ast_seal` | `foo` → `_foo` + verify zero external callers |

All share the same pipeline: **identify** (tree-sitter via `axm-ast`) → **blast radius** (`ast_callers`) → **transform** (libcst) → **validate** (`cst.parse_module()` + `audit(lint)`) → **write atomically** (`batch_edit`) → **rollback on error**.

## Installation

```bash
uv add axm-anvil
```

Or as a workspace dependency in `pyproject.toml`:

```toml
[project]
dependencies = ["axm-anvil"]

[tool.uv.sources]
axm-anvil = { workspace = true }
```

## Quick Start

CLI:

```bash
axm-anvil move src/mylib/core/models.py src/mylib/core/services.py \
    UserService,_validate_input --dry-run
```

Python / MCP:

```python
from axm_anvil import MoveTool

result = MoveTool().execute(
    path=".",
    symbols="UserService,_validate_input",
    from_file="src/mylib/core/models.py",
    to_file="src/mylib/core/services.py",
    dry_run=True,
)
print(result.data["moved"])
```

## Development

This package is part of the **axm-draft-workspace** uv workspace.

```bash
# Run tests for this package
uv run pytest --package axm-anvil

# From workspace root
make test-axm-anvil
```

## License

Apache-2.0 — © 2026 AXM Protocols
