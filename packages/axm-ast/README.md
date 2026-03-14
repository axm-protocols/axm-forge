# axm-ast

**Python AST introspection CLI for AI agents, powered by tree-sitter.**

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ast/axm-audit.json" alt="axm-audit"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ast/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ast/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-ast/"><img src="https://img.shields.io/pypi/v/axm-ast" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://forge.axm-protocols.io/ast/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

## Features

- 🔬 **Describe** — Full package introspection: functions, classes, imports, variables
- 🗜 **Compress** — AI-friendly compressed view: signatures + docstrings + `__all__`
- 📊 **Graph** — Import dependency graph with Mermaid output
- 🔍 **Search** — Semantic symbol lookup by name, return type, kind, or base class
- 📞 **Callers** — "Who calls this function?" via tree-sitter call-site detection
- 📋 **Context** — One-shot project dump: stack, patterns, module ranking
- 💥 **Impact** — Change impact analysis: callers + graph + test mapping
- 📖 **Docs** — One-shot documentation tree dump with progressive disclosure (toc/summary/full) and page filtering
- 💀 **Dead code** — Detect unreferenced symbols with smart exemptions (dict dispatch, entry points, test callers, lazy imports)
- 🚀 **Flows** — Entry point detection (cyclopts, click, Flask, FastAPI, pytest, `__main__`), BFS execution flow tracing with cross-module resolution and optional source code enrichment (`detail=source`)
- 🔀 **Diff** — Structural branch diff at symbol level (added/modified/removed via git worktrees)
- 🏗️ **Workspace** — Multi-package workspace support (auto-detects `uv` workspaces)
- ⭐ **Rank** — PageRank-based symbol importance scoring
- 📄 **Stub** — `.pyi`-like stub generation for any package

## Installation

```bash
uv add axm-ast
```

## Quick Start

```bash
# One-shot project context for AI agents
axm-ast context src/mylib
axm-ast context src/mylib --slim    # compact top-5 overview

# Describe a package at different detail levels
axm-ast describe src/mylib
axm-ast describe src/mylib --detail full
axm-ast describe src/mylib --compress
axm-ast describe src/mylib --detail toc               # table-of-contents
axm-ast describe src/mylib --modules core,tools        # filter by module
axm-ast describe src/mylib --detail toc --modules core # combined

# Visualize import graph as Mermaid
axm-ast graph src/mylib --format mermaid

# Find all callers of a function
axm-ast callers src/mylib --symbol my_function

# Change impact analysis
axm-ast impact src/mylib --symbol my_function

# Workspace: cross-package analysis (auto-detected)
axm-ast context /path/to/workspace   # all packages at once
axm-ast callers /path/to/workspace --symbol ToolResult
axm-ast graph /path/to/workspace --format mermaid

# Detect dead code
axm-ast dead-code src/mylib
axm-ast dead-code src/mylib --json
axm-ast dead-code src/mylib --include-tests  # also scan test modules as targets

# Dump all project documentation in one shot
axm-ast docs .
axm-ast docs . --detail toc              # heading scan (~500 tokens)
axm-ast docs . --detail summary          # headings + first sentences
axm-ast docs . --pages architecture      # filter by page name
axm-ast docs . --tree                    # tree only
axm-ast docs . --json                    # JSON output

# Structural diff between branches
axm-ast diff main..feature src/mylib
axm-ast diff main..feature src/mylib --json

# Detect entry points and trace execution flows
axm-ast flows src/mylib
axm-ast flows src/mylib --trace main          # BFS flow from entry point
axm-ast flows src/mylib --trace main --detail source  # include function source code
axm-ast flows tests/ --trace test_foo --cross-module  # resolve sibling-package imports
axm-ast flows src/mylib --trace main --json
```

### Example: `axm-ast context`

```
📋 mylib
  layout: src (16 modules, 151 functions, 9 classes)
  python: >=3.12

🔧 Stack
  cli: cyclopts     models: pydantic     tests: pytest
  lint: ruff         types: mypy          packaging: hatchling

📦 Modules (ranked)
  cli               ★★★★★  (describe, inspect, graph, search, callers...)
  core.analyzer     ★★★★☆  (analyze_package, build_import_graph...)
  core.context      ★★★★☆  (detect_stack, build_context...)
  core.docs         ★★★☆☆  (discover_docs, build_docs_tree...)
```

### Example: `axm-ast impact`

```
💥 Impact analysis for 'analyze_package' — HIGH

  📍 Defined in: core.analyzer (L38)
  📞 Direct callers (7): cli, core.context, core.impact
  📄 Affected modules (5): axm_ast, cli, core, core.context, core.impact
  🧪 Tests to rerun (7): test_analyzer, test_callers, test_compress...
  📦 Re-exported in (5): axm_ast, cli, core, core.context, core.impact
```

## CLI Commands

| Command | Description |
|---|---|
| `axm-ast describe` | Introspect a package (toc / summary / detailed / full / compress), optional `--modules` filter |
| `axm-ast inspect` | Inspect a single module file |
| `axm-ast graph` | Visualize import dependency graph (text / mermaid / json) |
| `axm-ast search` | Search symbols by name, return type, kind, or base class |
| `axm-ast callers` | Find all call-sites of a symbol |
| `axm-ast context` | One-shot project context dump for AI agents |
| `axm-ast impact` | Change impact analysis for a symbol |
| `axm-ast dead-code` | Detect unreferenced symbols with smart exemptions |
| `axm-ast flows` | Detect entry points and trace execution flows (`--detail source` for code enrichment) |
| `axm-ast diff` | Structural branch diff at symbol level (base..head) |
| `axm-ast docs` | One-shot documentation tree dump (README + mkdocs + docs/) |
| `axm-ast stub` | Generate `.pyi`-like stubs |
| `axm-ast version` | Show version |

All commands support `--json` for machine-readable output.

## Python API

```python
from axm_ast import analyze_package, search_symbols

pkg = analyze_package("src/mylib")
results = search_symbols(pkg, returns="str")
for fn in results:
    print(f"{fn.name}: {fn.signature}")
```

Use `get_package` instead of `analyze_package` to avoid re-parsing the same
package multiple times in a session:

```python
from axm_ast.core import get_package, clear_cache

pkg = get_package("src/mylib")  # parses on first call
pkg = get_package("src/mylib")  # cache hit — instant
clear_cache()                    # force re-parse on next call
```

## Development

This package is part of the [**axm-forge**](https://github.com/axm-protocols/axm-forge) workspace.

```bash
git clone https://github.com/axm-protocols/axm-forge.git
cd axm-forge
uv sync --all-groups
uv run --package axm-ast --directory packages/axm-ast pytest -x -q
```

📖 **[Full documentation](https://forge.axm-protocols.io/ast/)**

## License

Apache-2.0 — © 2026 axm-protocols
