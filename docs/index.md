---
hide:
  - navigation
  - toc
---

# axm-git

<p align="center">
  <strong>Deterministic Git workflows for AI agents</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-git/actions/workflows/ci.yml">
    <img src="https://github.com/axm-protocols/axm-git/actions/workflows/ci.yml/badge.svg" alt="CI" />
  </a>
  <a href="https://coveralls.io/github/axm-protocols/axm-git?branch=main">
    <img src="https://coveralls.io/repos/github/axm-protocols/axm-git/badge.svg?branch=main" alt="Coverage" />
  </a>
  <a href="https://pypi.org/project/axm-git/">
    <img src="https://img.shields.io/pypi/v/axm-git" alt="PyPI" />
  </a>
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+" />
</p>

---

## Features

- 🔍 **Preflight** — Structured working tree status with diff summary
- 📦 **Commit** — Batched atomic commits with auto-retry on pre-commit fixes
- 🏷️ **Tag** — One-shot semver tagging from Conventional Commits
- 🪝 **Hooks** — Lifecycle hook actions (create-branch, commit-phase, merge-squash) auto-discovered via entry-points

## Installation

```bash
uv add axm-git
```

## Quick Start

```python
# Check what changed
git_preflight(path="/path/to/repo")
# → {files: [{path: "foo.py", status: "M"}, ...], clean: false}

# Commit in batches
git_commit(path="/path/to/repo", commits=[
    {"files": ["src/foo.py"], "message": "feat: add foo"},
    {"files": ["tests/test_foo.py"], "message": "test: add foo tests"},
])

# Tag a release
git_tag(path="/path/to/repo")
# → {tag: "v0.2.0", bump: "minor", pushed: true}
```

---

<div style="text-align: center; margin: 2rem 0;">
  <a href="tutorials/getting-started/" class="md-button md-button--primary">Get Started →</a>
  <a href="reference/api/" class="md-button">API Reference</a>
</div>
