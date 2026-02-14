# axm-ast

**Python AST introspection CLI for AI agents, powered by tree-sitter.**

<p align="center">
  <a href="https://github.com/axm-protocols/axm-ast/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-ast/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/axm-protocols/axm-ast/actions/workflows/axm-init.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-ast/gh-pages/badges/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-ast/actions/workflows/axm-audit.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-ast/gh-pages/badges/axm-audit.json" alt="axm-audit"></a>
  <a href="https://coveralls.io/github/axm-protocols/axm-ast?branch=main"><img src="https://coveralls.io/repos/github/axm-protocols/axm-ast/badge.svg?branch=main" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-ast/"><img src="https://img.shields.io/pypi/v/axm-ast" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://axm-protocols.github.io/axm-ast/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
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
- 📖 **Docs** — One-shot documentation tree dump: README + mkdocs + all pages
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

# Describe a package at different detail levels
axm-ast describe src/mylib
axm-ast describe src/mylib --detail full
axm-ast describe src/mylib --compress

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

# Dump all project documentation in one shot
axm-ast docs .
axm-ast docs . --tree   # tree only
axm-ast docs . --json   # JSON output
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
| `axm-ast describe` | Introspect a package (summary / detailed / full / compress) |
| `axm-ast inspect` | Inspect a single module file |
| `axm-ast graph` | Visualize import dependency graph (text / mermaid / json) |
| `axm-ast search` | Search symbols by name, return type, kind, or base class |
| `axm-ast callers` | Find all call-sites of a symbol |
| `axm-ast context` | One-shot project context dump for AI agents |
| `axm-ast impact` | Change impact analysis for a symbol |
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

## Development

```bash
git clone https://github.com/axm-protocols/axm-ast.git
cd axm-ast
uv sync --all-groups
uv run pytest           # 323 tests
uv run mypy src/ tests/ # type check
uv run ruff check src/  # lint
```

## License

Apache-2.0 — © 2026 axm-protocols
