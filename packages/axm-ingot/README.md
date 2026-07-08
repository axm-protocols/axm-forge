<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>axm-ingot — Shared helper library for the AXM forge</strong>
</p>


<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ingot/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ingot/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ingot/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-ingot/"><img src="https://img.shields.io/pypi/v/axm-ingot" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://forge.axm-protocols.io/ingot/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

`axm-ingot` is the AXM forge's **shared helper library**: the single home for
small, general-purpose functions that more than one package needs. Instead of
copy-pasting the same logic into `axm-ast`, `axm-audit`, `axm-init` and
`axm-anvil` — and testing it N times, inconsistently — the logic lives here
once, is tested once, and is imported as a normal workspace dependency.

It is a **pure library**: no CLI, no MCP tool, no side effects. Just typed,
import-ready helpers.

📖 **[Full documentation](https://forge.axm-protocols.io/ingot/)**

## Why it exists

A monorepo accumulates duplication: the same "walk up to the project root",
"read `[tool.uv.workspace].members`", "resolve the workspace members" snippets
reappear in package after package, each with its own subtle bugs and its own
half-tested copy. `axm-ingot` is the deliberate counter-move — a thin,
dependency-light **ingot of common code** that downstream packages melt into
their own logic:

- **Factor once, fix once** — a bug fixed here is fixed everywhere.
- **Test once, trust everywhere** — helpers are covered in this package, so
  consumers don't re-test the same primitive.
- **Stable public surface** — consumers import from `axm_ingot`, not from each
  other, keeping the dependency graph a tree (no cross-tool coupling).

Today the shared surface is uv-workspace resolution; the library grows by
**promotion** — when a helper proves useful to a second package, it moves here.

## What belongs here (the light-leaf invariant)

`axm-ingot` is a **dependency-graph leaf** imported across the whole galaxy. Its
value depends on staying **light**: every consumer that imports it for one small
helper inherits *all* of its dependencies. A fat leaf is no longer a leaf.

**Hard rule — a helper may be promoted into `axm-ingot` only if its dependencies
are stdlib-only** — it adds **no dependency at all**. `dependencies` here stays
empty. Even Pydantic — a near-universal AXM dependency — does **not** belong:
it is still a dependency, and adding it breaks the leaf invariant. Value objects
here are frozen `@dataclass`, not `BaseModel`.

| Belongs in ingot ✅ | Does **not** belong ❌ |
|---|---|
| stdlib-only (`pathlib`, `tomllib`, `re`, `dataclasses`, `json`…) | pulls `httpx`, `pandas`, `torch`, a DB driver, an SDK… |
| frozen `@dataclass` value objects | `pydantic` models (Pydantic is a dependency — a fat leaf is no longer a leaf) |
| e.g. `resolve_workspace` (tomllib + pathlib) | e.g. `request_with_retry` (needs `httpx`) |

A reusable-but-heavy helper does **not** come here even when it has several
consumers: keep it `reuse_in_place` (import it from the package that owns it), or
give it a **thematic light lib** of its own (e.g. an `axm-net` for resilient
HTTP) — never the generic leaf. The Rule of Three (≥ 2 consumers) is *necessary*
for promotion but **not sufficient**; the dependency gate is the second lock.

## Features

- **uv-workspace resolution** — `resolve_workspace()` parses
  `[tool.uv.workspace]`, expands member globs, subtracts `exclude`, keeps only
  directories carrying a `pyproject.toml`, and returns members sorted by name.
- **Project-root discovery** — `find_project_root()` walks parents to the first
  ancestor holding any `pyproject.toml` (never returns `None`);
  `find_workspace_root()` finds the nearest uv-workspace root specifically.
- **Pure parsing primitive** — `parse_workspace_members()` returns the raw,
  unexpanded member strings from pyproject text, with no filesystem access.
- **Typed value objects** — frozen `ResolvedWorkspace` and `Member` dataclasses
  describe the resolved result.
- **Defensive by design** — a missing, malformed, non-UTF-8, or otherwise
  unreadable `pyproject.toml`, and hostile member globs (absolute paths,
  patterns `Path.glob` rejects), all degrade to empty/`None` results rather than
  raising.
- **Modern Python** — 3.12+ with strict typing, zero runtime dependencies
  beyond the standard library.

## Installation

```bash
uv add axm-ingot
```

Or, as a sibling package inside the workspace, declare it as a workspace
dependency in your `pyproject.toml`:

```toml
[project]
dependencies = ["axm-ingot"]

[tool.uv.sources]
axm-ingot = { workspace = true }
```

## Quick Start

`axm-ingot` is a library — you import its helpers, there is no command to run.

```python
from pathlib import Path

from axm_ingot import (
    find_project_root,
    find_workspace_root,
    resolve_workspace,
)

# Walk up to the nearest project root (any pyproject.toml ancestor).
root = find_project_root(Path("packages/axm-ast/src/axm_ast/core"))

# Resolve a uv workspace into its sorted members.
workspace = resolve_workspace(root)
if workspace is not None:
    for member in workspace.members:
        print(member.name, "->", member.path)

# Or just locate the nearest uv-workspace root.
ws_root = find_workspace_root(Path.cwd())
```

The pure parsing primitive is available from the `uv` subpackage when you only
have pyproject text (no filesystem):

```python
from axm_ingot.uv import parse_workspace_members

members = parse_workspace_members('[tool.uv.workspace]\nmembers = ["packages/*"]\n')
# ['packages/*']  — raw, unexpanded
```

## Public API

| Symbol | Kind | Description |
|---|---|---|
| `resolve_workspace(dir)` | function | Resolve a uv workspace → `ResolvedWorkspace \| None` |
| `find_project_root(start)` | function | Nearest ancestor with any `pyproject.toml` (never `None`) |
| `find_workspace_root(start)` | function | Nearest uv-workspace root → `Path \| None` |
| `parse_workspace_members(text)` | function | Raw `members` from pyproject text (`axm_ingot.uv`) |
| `ResolvedWorkspace` | dataclass | `{root, members}` — a resolved workspace |
| `Member` | dataclass | `{name, path}` — one workspace member |

## Development

This package is part of the [**axm-forge**](https://github.com/axm-protocols/axm-forge) workspace.

```bash
git clone https://github.com/axm-protocols/axm-forge.git
cd axm-forge
uv sync --all-groups
uv run --package axm-ingot --directory packages/axm-ingot pytest -x -q
```

## License

Apache-2.0 — © 2026 axm-protocols
