---
hide:
  - navigation
  - toc
---

# axm-echo

<p align="center">
  <strong>Neural similarity & echo detection over code corpora (MiniLM + scikit-learn).</strong>
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
# echo is neural by default — the install ships torch + sentence-transformers
# (MiniLM) alongside numpy + scikit-learn.
uv add axm-echo
```

The neural `st` backend is the in-process default. The `tfidf` backend stays
pure-CPU and never loads torch, for callers that want to skip the model.

## Quick Start

```python
from axm_echo import embed, extract_monorepo, neighbors

# 1. Build a corpus of public symbols across the configured workspaces
#    (driven by ~/.axm/echo.toml, falling back to the current dir).
symbols = extract_monorepo()
texts = [s["embed_text"] for s in symbols]

# 2. Embed it. "st" (MiniLM) is the neural default; "tfidf" stays pure-CPU.
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
- ✅ **Liveable `echo_code` report** — bounded `--top-n` display (the neural
  pass still finds them all, only the output is capped; the total stays
  visible), `--max-cluster-size` rejection of union-find over-merges, and an
  acknowledged-cluster **waiver** workflow (`[[tool.axm-echo.acknowledged]]`
  in the scan-root `pyproject.toml`) that excludes intended echoes and reports
  stale waivers to retire
- ✅ **`echo_check` intent retrieval** — the `axm echo_check` tool
  (MCP + CLI + DAG node) embeds a free-form intention and returns the top-k
  nearest monorepo symbols with their docstrings, each tagged with a location
  verdict (reuse canonical / reuse in place / promotable); it does the
  retrieval, leaving the use / extend / nothing decision to the caller
- ✅ **Structural similarity** — `statement_set` / `jaccard_similarity`
  (with `flatten_body` / `normalize_dump`) compare two `ast.FunctionDef`
  bodies by Jaccard over constant/identifier-normalized statement-sets;
  100% structural, pure stdlib, never loads torch
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
