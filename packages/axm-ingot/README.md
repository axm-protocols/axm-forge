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

It is a Python library with no CLI or MCP tool. Workspace, suite and console
helpers read the filesystem; they do not write files or launch processes.

## Features

- **uv-workspace resolution** — `resolve_workspace()` parses
  `[tool.uv.workspace]`, expands member globs, subtracts `exclude`, keeps only
  directories carrying a `pyproject.toml`, and returns members sorted by directory basename.
- **Project-root discovery** — `find_project_root()` walks parents to the first
  ancestor holding any `pyproject.toml` (never returns `None`);
  `find_workspace_root()` finds the nearest uv-workspace root specifically.
- **Pure parsing primitive** — `parse_workspace_members()` returns the raw,
  unexpanded member strings from pyproject text, with no filesystem access.
- **Typed value objects** — frozen `ResolvedWorkspace` and `Member` dataclasses
  describe the resolved result.
- **Compact rendering** — primitives plus the submodule-level `render_result`
  walker for readable text. Preserve structured data when exact types matter.
- **Console and test helpers** — `console_script` locates a script without
  executing it; `tally_outcomes` counts supplied outcome lines.
- **Function-specific fallbacks** — pyproject read/parse errors and rejected
  glob patterns have documented fallbacks. Arbitrary inputs and filesystem
  operations do not share a blanket never-raises guarantee.
- **Modern Python** — 3.12+ with strict typing, zero runtime dependencies
  beyond the standard library.

## Installation

Requires Python 3.12 or newer. In a Python project managed by uv:

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

Parse workspace declarations without creating any files:

```bash
uv run python - <<'PY'
from axm_ingot.uv import parse_workspace_members

members = parse_workspace_members('[tool.uv.workspace]\nmembers = ["packages/*"]\n')
print(members)
PY
```

This prints `['packages/*']`: the declared patterns, without glob expansion or
filesystem access.

## Usage

### Discover workspace members

Run this from a project directory to locate its nearest project and enclosing
uv workspace:

```python
from pathlib import Path

from axm_ingot import (
    find_project_root,
    find_workspace_root,
    resolve_workspace,
)

# Walk up to the nearest project root (any pyproject.toml ancestor).
root = find_project_root(Path.cwd())
print("Project:", root)

# Resolve a uv workspace into its sorted members.
ws_root = find_workspace_root(Path.cwd())
workspace = resolve_workspace(ws_root) if ws_root is not None else None
if workspace is not None:
    for member in workspace.members:
        print(member.name, "->", member.path)

else:
    print("No uv workspace found")
```

`Member.name` is the directory basename, not the distribution name. Use paths
as keys when two members may share a basename. `find_project_root` falls back
to the resolved starting directory if no project exists.

### Public API

| Symbol | Kind | Description |
|---|---|---|
| `resolve_workspace(dir)` | function | Resolve a uv workspace → `ResolvedWorkspace \| None` |
| `find_project_root(start)` | function | Nearest ancestor with any `pyproject.toml` (never `None`) |
| `find_workspace_root(start)` | function | Nearest uv-workspace root → `Path \| None` |
| `parse_workspace_members(text)` | function | Raw `members` from pyproject text (`axm_ingot.uv`) |
| `ResolvedWorkspace` | dataclass | `{root, members}` — a resolved workspace |
| `Member` | dataclass | `{name, path}` — one workspace member |
| `header`, `labeled_block`, `compact_table` | functions | Compose readable text |
| `truncate`, `format_count`, `format_size` | functions | Shorten text and format quantities |
| `format_duration` | function | Milliseconds → duration text |
| `console_script` | function | Interpreter directory → PATH → unchanged name |
| `tally_outcomes` | function | Count failed/error/skipped/unknown lines |

`render_result` and `record_table` are imported from `axm_ingot.render`, not
from the package root. See the [API reference](docs/reference/api.md) for exact
signatures, import paths and limitations, and the
[temporary-workspace tutorial](docs/tutorials/getting-started.md) for a runnable
example. Internal suite-discovery utilities live in `axm_ingot.suite`.

### Why it exists

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
  other, avoiding cross-tool coupling.

The shared surface covers workspace discovery, text rendering, durations,
console-script lookup and pytest outcome tallies. The library grows by
**promotion**, subject to reuse and dependency checks.

### What belongs here (the light-leaf invariant)

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

## Documentation

- [Published documentation](https://forge.axm-protocols.io/ingot/)
- [Getting started](docs/tutorials/getting-started.md): a temporary workspace.
- [Promote a helper](docs/howto/promote-a-helper.md): reuse and dependency gates.
- [API reference](docs/reference/api.md): imports, signatures and fallbacks.
- [Architecture](docs/explanation/architecture.md): the shared-library boundaries.

The MkDocs home page is [docs/index.md](docs/index.md), separate from this README.

## Development

This package is part of the [**axm-forge**](https://github.com/axm-protocols/axm-forge) workspace.

```bash
git clone https://github.com/axm-protocols/axm-forge.git
cd axm-forge
uv sync --all-packages --all-groups
uv run --package axm-ingot --directory packages/axm-ingot pytest -x -q
```

## License

Licensed under Apache-2.0. See [LICENSE](LICENSE).
