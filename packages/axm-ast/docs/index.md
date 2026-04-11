<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="140" />
</p>

<h1 align="center">axm-ast</h1>
<p align="center"><strong>Python AST introspection CLI for AI agents, powered by tree-sitter.</strong></p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ast/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ast/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ast/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-ast/"><img src="https://img.shields.io/pypi/v/axm-ast" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+" />
</p>

---

## What it does

`axm-ast` gives AI agents (and humans) instant, structured access to any Python codebase. One command and your agent knows every function, class, import, and dependency — no manual exploration needed.

## Quick Example

```bash
$ axm-ast context src/mylib

📋 mylib
  layout: src (16 modules, 151 functions, 9 classes)
  python: >=3.12

🔧 Stack
  cli: cyclopts     models: pydantic     tests: pytest
  lint: ruff         types: mypy          packaging: hatchling

📦 Modules (ranked)
  cli               ★★★★★  (describe, inspect, graph, search...)
  core.analyzer     ★★★★☆  (analyze_package, build_import_graph...)
  core.docs         ★★★☆☆  (discover_docs, build_docs_tree...)
```

## Features

- 🔬 **Describe** — Full package introspection with 4 detail levels + compressed AI mode + module filtering
- 📊 **Graph** — Import dependency visualization (text, Mermaid, JSON)
- 🔍 **Search** — Semantic symbol lookup by name, return type, kind, or base class
- 📞 **Callers** — Tree-sitter call-site detection: "who calls this function?"
- 📋 **Context** — One-shot project dump: stack, patterns, module ranking
- 💥 **Impact** — Change impact analysis: callers + graph + test mapping
- 💀 **Dead code** — Detect unreferenced symbols with smart exemptions (test callers, lazy imports, dict dispatch, entry points)
- 🔀 **Diff** — Structural branch diff at symbol level (added/modified/removed)
- 🏗️ **Workspace** — Multi-package workspace support (auto-detects `uv` workspaces)
- 📖 **Docs** — One-shot documentation tree dump with progressive disclosure (toc/summary/full) and page filtering
- ⭐ **Rank** — PageRank-based symbol importance scoring
- 📄 **Stub** — `.pyi`-like stub generation

## Learn More

- [Quick Start Tutorial](tutorials/quickstart.md)
- [Describe a Package](howto/describe.md)
- [Analyze Change Impact](howto/impact.md)
- [How-To Guides](howto/index.md)
- [Use via MCP](howto/mcp.md)
- [Architecture](explanation/architecture.md)
- [Output Formats](explanation/formats.md)
- [CLI Reference](reference/cli.md)
