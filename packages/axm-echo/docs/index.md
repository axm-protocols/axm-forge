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
from axm_echo import __version__

print(f"axm-echo v{__version__}")
```

## Features

- ✅ **Light base install** — numpy + scikit-learn, no torch
- ✅ **Optional `[neural]` extra** — torch + sentence-transformers on demand
- ✅ **Modern Python** — 3.12+ with strict typing
- ✅ **Tested** — Full coverage with pytest

---

<div style="text-align: center; margin: 2rem 0;">
  <a href="tutorials/getting-started/" class="md-button md-button--primary">Get Started →</a>
  <a href="reference/cli/" class="md-button">Reference</a>
</div>
