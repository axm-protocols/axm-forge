# axm-anvil

**Deterministic CST-based refactoring toolkit for Python.**

<p align="center">
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-anvil/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-anvil/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-anvil/coverage.json" alt="Coverage"></a>
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

- 🔨 **`anvil_move`** — Move classes, functions, or constants between files with transitive dependency resolution (imports, constants, helpers)
- ✏️ **`anvil_rename`** — Rename top-level symbols in place and rewrite cross-file callers atomically (definition + internal usages + `from mod import Old` imports and usages in every caller)
- 🔁 **Smart import merging** — Uses `AddImportsVisitor` to combine imports from the same module instead of duplicating
- 🧹 **Scope-aware orphan cleanup** — Source file's unused imports are removed via `ruff check --select F401 --fix`
- 📐 **Topological constant ordering** — Dependencies are always inserted before their dependents
- 🛡️ **Atomic writes** — All modifications computed in memory, validated via `cst.parse_module()`, then applied via a single `batch_edit` call (all-or-nothing)
- 🔗 **Attribute-style caller rewrites** — Rewrites `old_module.Symbol` chains (including `import ... as` aliases) to the new module, preserving method/subscript chains and skipping shadowed names via `ScopeProvider`
- 🪢 **`--reexport` mode** — Leaves callers untouched and injects a `from new_module import <Symbol>  # re-export for backwards compat` shim into the source module for gradual migration
- 🎯 **Overload-aware** — Detects `@overload` companions and moves them together as an indivisible group
- 📦 **Lossless formatting** — Comments, whitespace, and trailing commas preserved exactly via libcst round-trip
- 🤝 **Complementary to `axm-ast`** — Builds the workspace-wide module graph via `analyze_workspace` + `build_workspace_module_graph` to detect newly-introduced cross-package import cycles
- ✏️ **`--rename` on move** — Rename moved definitions in flight (JSON `{"Old": "New"}`); references, `__all__` entries, and string forward-references are all rewritten to the new name
- 📍 **`--insert-after`** — Splice moved blocks after a named target symbol instead of appending at end-of-file
- 🚫 **`--no-include-helpers`** — Skip auto-copying local helpers/constants into the target (imports are still copied); emits a warning listing the un-copied names
- 🧭 **Edge-case awareness** — Syncs `__all__` (never created spontaneously), preserves `try/except` conditional imports verbatim, converts relative imports to absolute on cross-package moves, and warns on side-effect decorators (`@app.route`, `@pytest.fixture`…), string forward-references, and pytest fixture-scope breaks

## Roadmap

### Planned tools

`anvil_move`, `anvil_rename`, and `anvil_extract` are the shipped
operations. The tools below are **not yet implemented** — they are listed
here to convey the intended direction.

| Tool | Description | Status |
|---|---|---|
| `anvil_move` | Move symbols between files | shipped |
| `anvil_rename` | Rename a top-level symbol in place; rewrite cross-file callers (imports + usages) | shipped |
| `anvil_extract` | Extract symbols into a new module (created on disk) with their transitive dependencies | shipped |
| `anvil_split` | Split a module into N sub-modules | planned |
| `anvil_merge` | Merge N modules into one | planned |
| `anvil_promote` | `_foo` → `foo` + add `__all__` + update imports | planned |
| `anvil_seal` | `foo` → `_foo` + verify zero external callers | planned |

All share the same pipeline: **identify** (libcst block extraction) → **blast radius** (libcst caller discovery + the workspace module graph from `axm-ast`) → **transform** (libcst) → **validate** (`cst.parse_module()` + `ruff check --fix`) → **write atomically** (`batch_edit`) → **rollback on error**.

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

CLI — preview a move (positional or flag form, both accepted):

```bash
axm-anvil move src/mylib/core/models.py src/mylib/core/services.py \
    UserService,_validate_input --dry-run
```

Rename while moving, and place the result after an existing symbol:

```bash
axm-anvil move \
    --from-file src/mylib/core/models.py \
    --to-file   src/mylib/core/services.py \
    --symbols   UserService \
    --rename    '{"UserService": "AccountService"}' \
    --insert-after existing_service
```

Move without dragging local helpers along (imports are still copied):

```bash
axm-anvil move src/mylib/a.py src/mylib/b.py Widget --no-include-helpers
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
print(result.data["warnings"])  # __all__ sync, conditional imports, decorators, …
```

See the [CLI Reference](docs/reference/cli.md) for every flag and the warnings each one can emit.

## Development

This package is part of the **axm-forge** uv workspace.

```bash
# Run tests for this package
uv run --package axm-anvil --directory packages/axm-anvil pytest

# From workspace root
make test-anvil
```

## License

Apache-2.0 — © 2026 AXM Protocols
