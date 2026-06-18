<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="140" />
</p>

<h1 align="center">axm-ingot</h1>
<p align="center"><strong>Shared helper library for the AXM forge.</strong></p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ingot/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ingot/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ingot/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-ingot/"><img src="https://img.shields.io/pypi/v/axm-ingot" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+" />
</p>

---

## What it does

`axm-ingot` is the AXM forge's **shared helper library** — the single home for
small, general-purpose functions that more than one package needs. Logic that
would otherwise be copy-pasted (and re-tested) across `axm-ast`, `axm-audit`,
`axm-init` and `axm-anvil` lives here once, is tested once, and is imported as a
normal workspace dependency. It is a **pure library**: no CLI, no MCP tool, no
side effects.

| Helper | Kind | What it returns |
|---|---|---|
| `resolve_workspace(dir)` | function | A `ResolvedWorkspace` (sorted, exclude-aware) or `None` |
| `find_project_root(start)` | function | Nearest ancestor with any `pyproject.toml` (never `None`) |
| `find_workspace_root(start)` | function | Nearest uv-workspace root, or `None` |
| `parse_workspace_members(text)` | function | Raw `members` strings from pyproject text |
| `ResolvedWorkspace` / `Member` | dataclass | Frozen value objects describing the result |

## Quick Example

```python
from pathlib import Path

from axm_ingot import resolve_workspace, find_workspace_root

# Resolve a uv workspace to its members (sorted, exclude-aware, require_pyproject)
workspace = resolve_workspace(Path("/path/to/workspace"))
if workspace is not None:
    for member in workspace.members:
        print(member.name, "->", member.path)

# Walk up from any directory to the enclosing uv-workspace root
root = find_workspace_root(Path.cwd())
```

## Features

- **uv-workspace resolution** — `resolve_workspace` parses
  `[tool.uv.workspace]`, expands `members` globs, subtracts `exclude`, enforces
  `require_pyproject`, and returns members sorted by name
- **Project-root discovery** — `find_project_root` walks parents to the first
  `pyproject.toml` of any kind, always returning a `Path` (never `None`);
  `find_workspace_root` stops at the first `[tool.uv.workspace]` specifically
- **Raw members parsing** — `parse_workspace_members` reads the declared
  member strings from pyproject text verbatim (no globs, no filesystem)
- **Frozen value types** — `ResolvedWorkspace` and `Member` are stdlib
  `@dataclass(frozen=True)` records
- **Zero dependencies** — stdlib only (`tomllib`, `pathlib`, `dataclasses`); a
  true leaf of the forge dependency graph
- **Defensive** — an absent or malformed `pyproject.toml` returns `None`/`[]`,
  never raises

## Learn More

- [Getting Started Tutorial](tutorials/getting-started.md)
- [List a workspace's members](howto/index.md)
- [API Reference](reference/cli.md)
- [Architecture & Design Decisions](explanation/architecture.md)
