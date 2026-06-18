---
hide:
  - navigation
  - toc
---

# axm-echo

<p align="center">
  <strong>Similarity & echo detection over code corpora (numpy/scikit-learn).</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge-workspace/actions/workflows/ci.yml">
    <img src="https://github.com/axm-protocols/axm-forge-workspace/actions/workflows/ci.yml/badge.svg" alt="CI" />
  </a>
  <a href="https://github.com/axm-protocols/axm-forge-workspace/actions/workflows/axm-quality.yml">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge-workspace/gh-pages/badges/axm-echo/axm-init.json" alt="axm-init" />
  </a>
  <a href="https://github.com/axm-protocols/axm-forge-workspace/actions/workflows/axm-quality.yml">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge-workspace/gh-pages/badges/axm-echo/axm-audit.json" alt="axm-audit" />
  </a>
  <a href="https://github.com/axm-protocols/axm-forge-workspace/actions/workflows/axm-quality.yml">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge-workspace/gh-pages/badges/axm-echo/coverage.json" alt="Coverage" />
  </a>
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+" />
</p>

---

## Installation

```bash
# Base install — numpy + scikit-learn only (no torch)
uv add axm-echo

# With the optional neural backend — torch + sentence-transformers
uv add "axm-echo[neural]"
```

## Quick Start

```python
from axm_echo import embed, extract_monorepo, neighbors

# 1. Build a corpus of public symbols across the configured workspaces
#    (driven by ~/.axm/echo.toml, falling back to the current dir).
symbols = extract_monorepo()
texts = [s["embed_text"] for s in symbols]

# 2. Embed it. "tfidf" stays pure-CPU (no torch); "st" uses MiniLM.
matrix = embed(texts, backend="tfidf")

# 3. Find the nearest neighbours of a symbol (exact cosine top-k).
for idx, score in neighbors(matrix[0], matrix, k=5):
    print(f"{score:.3f}  {symbols[idx]['qualname']}")
```

## Features

- ✅ **`echo_code` cross-package echo detection** — the `axm echo_code` tool
  (MCP + CLI + DAG node) clusters intent-equivalent duplicate symbols across
  packages, with the v7 anti-signals (trivial-accessor filter, parallel-API
  demotion, boilerplate-frequency demotion) applied
- ✅ **Two embedding backends** — `tfidf` (code, scikit-learn) and `st`
  (MiniLM `all-MiniLM-L6-v2`), selected by a registry
- ✅ **Exact neighbour search** — brute-force cosine matmul, no ANN
- ✅ **Light base install** — numpy + scikit-learn, no torch
- ✅ **Lazy neural backend** — torch is imported only inside the `st`
  backend (the `tfidf` path never loads it)
- ✅ **axm-ast corpus extractor** — public symbols with signature +
  docstring, `embed_text` falling back to code when undocumented
- ✅ **Scope loader** — `~/.axm/echo.toml`, graceful degradation to the
  current workspace
- ✅ **Modern Python** — 3.12+ with strict typing

---

<div style="text-align: center; margin: 2rem 0;">
  <a href="tutorials/getting-started/" class="md-button md-button--primary">Get Started →</a>
  <a href="reference/cli/" class="md-button">Reference</a>
</div>
