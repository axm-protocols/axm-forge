<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>axm-ast — Read-only source analysis for Python and optional TypeScript/TSX</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ast/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ast/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ast/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-ast/"><img src="https://img.shields.io/pypi/v/axm-ast" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://forge.axm-protocols.io/ast/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

uv run axm-ast helps developers and agents explore source code, find symbols and
review the impact of changes without editing the analyzed files. It provides
a standalone CLI, AXM tools and a Python API, with optional TypeScript/TSX
extraction.

## Features

- 🔬 **Describe** — Full package introspection: functions, classes, imports, variables
- 🗜 **Compress** — AI-friendly compressed view: signatures + docstrings + `__all__`
- 📊 **Graph** — Import dependency graph with Mermaid output
- 🔍 **Search** — Lexical symbol lookup by name, return type, kind, or base class
- 📞 **Callers** — "Who calls this function?" via tree-sitter call-site detection
- 📋 **Context** — One-shot project dump: stack, patterns, module ranking
- 💥 **Impact** — Change impact analysis: callers + graph + test mapping
- 📝 **Doc Impact** — Documentation health: doc refs, undocumented symbols, stale signatures
- 📖 **Docs** — One-shot documentation tree dump with progressive disclosure (toc/summary/full) and page filtering
- 💀 **Dead code** — Detect unreferenced symbols with smart exemptions (dict dispatch, positional args, entry points, test callers, lazy imports)
- 🚀 **Flows** — Entry point detection (cyclopts, click, Flask, FastAPI, pytest, `__main__`), BFS execution flow tracing with cross-module resolution and optional source code enrichment (`detail=source`)
- 🔀 **Diff** — Structural branch diff at symbol level (added/modified/removed via git worktrees)
- 🏗️ **Workspace** — Multi-package workspace support (auto-detects `uv` workspaces)
- ⭐ **Rank** — PageRank-based symbol importance scoring

## Installation

Requires Python 3.12 or newer. In a Python project managed by uv:

```bash
uv add axm-ast
```

## Quick Start

From the root of an existing Python project, after installation:

```bash
uv run axm-ast context . --depth 0
```

This prints a compact project overview with the highest-ranked modules.
The command reads your project without modifying its source files.

## Usage

### CLI examples

Run these from your project environment; replace `src/mylib`, symbol names
and Git refs with values from your project.

```bash
# One-shot project context for AI agents
uv run axm-ast context src/mylib               # full context (all modules + dependency graph)
uv run axm-ast context src/mylib --depth 0     # compact top-5 overview
uv run axm-ast context src/mylib --depth 1     # sub-packages with aggregate counts

# Describe a package at different detail levels
uv run axm-ast describe src/mylib
uv run axm-ast describe src/mylib --detail detailed
uv run axm-ast describe src/mylib --compress
uv run axm-ast describe src/mylib --detail toc --json               # table-of-contents
uv run axm-ast describe src/mylib --modules core,tools        # filter by module
uv run axm-ast describe src/mylib --detail toc --json --modules core # combined

# Visualize import graph as Mermaid
uv run axm-ast graph src/mylib --format mermaid

# Find all callers of a function
uv run axm-ast callers src/mylib --symbol my_function

# Change impact analysis
uv run axm-ast impact src/mylib --symbol my_function

# Workspace: cross-package analysis (auto-detected)
uv run axm-ast context /path/to/workspace   # all packages at once
uv run axm-ast callers /path/to/workspace --symbol ToolResult
uv run axm-ast graph /path/to/workspace --format mermaid
uv run axm-ast graph /path/to/workspace --format text

# Detect dead code
uv run axm-ast dead-code src/mylib
uv run axm-ast dead-code src/mylib --json
uv run axm-ast dead-code src/mylib --include-tests  # also scan test modules as targets

# Dump all project documentation in one shot
uv run axm-ast docs .
uv run axm-ast docs . --detail toc              # heading scan (~500 tokens)
uv run axm-ast docs . --detail summary          # headings + first sentences
uv run axm-ast docs . --pages architecture      # filter by page name
uv run axm-ast docs . --tree                    # tree only
uv run axm-ast docs . --json                    # JSON output

# Structural diff between branches
uv run axm-ast diff main..feature src/mylib
uv run axm-ast diff main..feature src/mylib --json

# Detect entry points and trace execution flows
uv run axm-ast flows src/mylib
uv run axm-ast flows src/mylib --trace main          # BFS flow from entry point
uv run axm-ast flows src/mylib --trace main --detail source  # include function source code
uv run axm-ast flows tests/ --trace test_foo --cross-module  # resolve sibling-package imports
uv run axm-ast flows src/mylib --trace main --json
```

#### Example: `axm-ast context`

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

#### Example: `axm-ast impact`

```
💥 Impact analysis for 'analyze_package' — HIGH

  📍 Defined in: core.analyzer (L38)
  📞 Direct callers (7): cli, core.context, core.impact
  📄 Affected modules (5): axm_ast, cli, core, core.context, core.impact
  🧪 Tests to rerun (7): test_analyzer, test_callers, test_compress...
  📦 Re-exported in (5): axm_ast, cli, core, core.context, core.impact
```

### CLI Commands

| Command | Description |
|---|---|
| `axm-ast describe` | Introspect a package (toc / summary / detailed / compress), optional `--modules` filter |
| `axm-ast inspect` | Inspect a symbol by name across a package (supports dotted paths, `--source` for source code) |
| `axm-ast graph` | Visualize import dependency graph (text / mermaid / json) |
| `axm-ast search` | Search symbols by name, return type, kind, or base class |
| `axm-ast callers` | Find all call-sites of a symbol |
| `axm-ast callees` | Find all call-sites *within* a symbol's body (inverse of `callers`) |
| `axm-ast context` | One-shot project context dump for AI agents |
| `axm-ast impact` | Change impact analysis for a symbol |
| `axm-ast dead-code` | Detect unreferenced symbols with smart exemptions |
| `axm-ast flows` | Detect entry points and trace execution flows (`--detail source` for code enrichment) |
| `axm-ast diff` | Structural branch diff at symbol level (base..head) |
| `axm-ast docs` | One-shot documentation tree dump (README + mkdocs + docs/) |
| `axm-ast version` | Show version |

Analysis commands support `--json`; `version` does not. Avoid combining it with text-only `--compress` or `impact --compact`. CLI and AXM tools have distinct defaults and response envelopes; see [MCP usage](docs/howto/mcp.md).

### Python API

```python
from pathlib import Path
from axm_ast import FunctionInfo, analyze_package, search_symbols

pkg = analyze_package(Path("src/mylib"))
results = search_symbols(pkg, returns="str")
for module, symbol in results:
    if isinstance(symbol, FunctionInfo):
        print(f"{module}.{symbol.name}: {symbol.signature}")
```

`analyze_package` auto-detects src-layout projects (i.e. `src/<pkg>/__init__.py`)
and sets the package root to the actual package directory under `src/` (e.g.
`src/axm_ast/`), so `pkg.name` and import resolution use the real package name
instead of `"src"`.

Use `get_package` instead of `analyze_package` to avoid re-parsing the same
package multiple times in a session:

```python
from pathlib import Path
from axm_ast.core.cache import get_package, clear_cache

pkg = get_package(Path("src/mylib"))  # parses on first call
pkg = get_package(Path("src/mylib"))  # validates the Python file fingerprint
clear_cache()                    # force re-parse on next call
```

### Scope and limitations

The tools do not edit analyzed source. Structural diff creates and cleans temporary git worktrees. Workspace aggregation is explicit per tool, not a property of every `path` argument. Python call matching is syntactic; impact and dead-code findings require review.

Install `uv add 'axm-ast[typescript]'` for `.ts`/`.tsx` extraction in a Node project root containing `package.json`. This checkout does not discover `.js`, `.jsx`, or `.svelte` files. The session cache watches Python files only; use fresh CLI processes for changed TypeScript sources. See [scope and languages](docs/howto/scope-and-languages.md).

## Documentation

Start with the [runnable tutorial](docs/tutorials/quickstart.md), [Python API guide](docs/reference/api.md), or [AXM tool contracts](docs/reference/tools.md). The README is the repository entry point; [docs/index.md](docs/index.md) is the MkDocs home page.

- [CLI reference](docs/reference/cli.md)
- [Architecture](docs/explanation/architecture.md)
- [Published documentation](https://forge.axm-protocols.io/ast/)

## Development

This package is part of the [**axm-forge**](https://github.com/axm-protocols/axm-forge) workspace.

```bash
git clone https://github.com/axm-protocols/axm-forge.git
cd axm-forge
uv sync --all-packages --all-groups
uv run --package axm-ast --directory packages/axm-ast pytest -x -q
```

From `packages/axm-ast`, run `mkdocs build --strict` in an environment
containing the package documentation dependencies to build its standalone site.

## License

Licensed under Apache-2.0. See [LICENSE](LICENSE).
