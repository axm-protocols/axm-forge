---
hide:
  - navigation
  - toc
---

# axm-ingot

<p align="center">
  <strong>Canonical shared helpers factored out of duplicated AXM code.</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge-workspace/actions/workflows/ci.yml">
    <img src="https://github.com/axm-protocols/axm-forge-workspace/actions/workflows/ci.yml/badge.svg" alt="CI" />
  </a>
  <a href="https://github.com/axm-protocols/axm-forge-workspace/actions/workflows/axm-quality.yml">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge-workspace/gh-pages/badges/axm-ingot/axm-init.json" alt="axm-init" />
  </a>
  <a href="https://github.com/axm-protocols/axm-forge-workspace/actions/workflows/axm-quality.yml">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge-workspace/gh-pages/badges/axm-ingot/axm-audit.json" alt="axm-audit" />
  </a>
  <a href="https://github.com/axm-protocols/axm-forge-workspace/actions/workflows/axm-quality.yml">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge-workspace/gh-pages/badges/axm-ingot/coverage.json" alt="Coverage" />
  </a>
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+" />
</p>

---

## Installation

```bash
uv add axm-ingot
```

## Quick Start

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

- ✅ **Canonical uv-workspace resolution** — `resolve_workspace` parses
  `[tool.uv.workspace]`, expands `members` globs, subtracts `exclude`, and
  enforces `require_pyproject`, returning members sorted by name
- ✅ **Raw members parsing** — `parse_workspace_members` reads the
  `[tool.uv.workspace].members` array from pyproject text verbatim (no glob
  expansion, no filesystem access), for callers that only need the declared
  member strings; defensive (returns `[]` on malformed TOML or absent table)
- ✅ **Workspace-root discovery** — `find_workspace_root` walks parents to the
  first `pyproject.toml` carrying a `[tool.uv.workspace]` section
- ✅ **Project-root discovery** — `find_project_root` walks parents to the first
  `pyproject.toml` of any kind, always returning a `Path` (start-dir fallback,
  never `None`); the counterpart used to anchor relative imports
- ✅ **Frozen value types** — `ResolvedWorkspace` and `Member` are stdlib
  `@dataclass(frozen=True)` records
- ✅ **Zero dependencies** — stdlib only (`tomllib`, `pathlib`, `dataclasses`);
  a true leaf of the forge dependency graph
- ✅ **Defensive** — an absent or malformed `pyproject.toml` returns `None`,
  never raises

---

<div style="text-align: center; margin: 2rem 0;">
  <a href="tutorials/getting-started/" class="md-button md-button--primary">Get Started →</a>
  <a href="reference/cli/" class="md-button">Reference</a>
</div>
