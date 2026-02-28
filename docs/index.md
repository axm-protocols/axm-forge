---
hide:
  - navigation
  - toc
---

# axm-ast

<p align="center">
  <strong>Python AST introspection CLI for AI agents, powered by tree-sitter.</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-ast/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-ast/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="https://axm-protocols.github.io/axm-init/explanation/check-grades/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-ast/gh-pages/badges/axm-init.json" alt="axm-init" /></a>
  <a href="https://axm-protocols.github.io/axm-audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-ast/gh-pages/badges/axm-audit.json" alt="axm-audit" /></a>
  <a href="https://coveralls.io/github/axm-protocols/axm-ast?branch=main"><img src="https://coveralls.io/repos/github/axm-protocols/axm-ast/badge.svg?branch=main" alt="Coverage" /></a>
  <a href="https://pypi.org/project/axm-ast/"><img src="https://img.shields.io/pypi/v/axm-ast" alt="PyPI" /></a>
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+" />
</p>

---

## What is axm-ast?

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
- 🏗️ **Workspace** — Multi-package workspace support (auto-detects `uv` workspaces)
- 📖 **Docs** — One-shot documentation tree dump: README + mkdocs + all pages
- ⭐ **Rank** — PageRank-based symbol importance scoring
- 📄 **Stub** — `.pyi`-like stub generation

---

<div style="text-align: center; margin: 2rem 0;">
  <a href="tutorials/quickstart/" class="md-button md-button--primary">Get Started →</a>
  <a href="reference/cli/" class="md-button">CLI Reference</a>
</div>
