---
hide:
  - navigation
  - toc
---

# axm-anvil

<p align="center">
  <strong>Deterministic CST-based refactoring toolkit for Python — move, rename, split, merge symbols atomically across files.</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml">
    <img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI" />
  </a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-anvil/axm-init.json" alt="axm-init" />
  </a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-anvil/axm-audit.json" alt="axm-audit" />
  </a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-anvil/coverage.json" alt="Coverage" />
  </a>
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+" />
</p>

---

## Installation

```bash
uv add axm-anvil
```

## Quick Start

Move a class and a private helper into another module, previewing first:

```bash
axm-anvil move src/mylib/models.py src/mylib/services.py \
    UserService,_validate_input --dry-run
```

## Features

- 🔨 **Deterministic moves** — Classes, functions, and constants moved with transitive dependency resolution (imports, constants, helpers), formatting preserved exactly via libcst
- ✏️ **Rename in flight** — `--rename '{"Old": "New"}'` rewrites the definition, every reference, `__all__`, and string forward-references
- 📍 **Placement control** — `--insert-after` splices moved blocks after a named symbol; `--no-include-helpers` skips copying local helpers
- 🧭 **Edge-case aware** — `__all__` sync, conditional-import preservation, relative→absolute import conversion on cross-package moves, and warnings for side-effect decorators, string forward-refs, and pytest fixture-scope breaks
- 🛡️ **Atomic & safe** — All edits computed in memory, validated, then written all-or-nothing; new import cycles are detected via `--check`

---

<div style="text-align: center; margin: 2rem 0;">
  <a href="tutorials/getting-started/" class="md-button md-button--primary">Get Started →</a>
  <a href="reference/cli/" class="md-button">Reference</a>
</div>
