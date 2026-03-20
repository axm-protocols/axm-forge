<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="140" />
</p>

<h1 align="center">axm-git</h1>
<p align="center"><strong>Deterministic Git workflows for AI agents.</strong></p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-git/axm-audit.json" alt="axm-audit"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-git/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-git/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-git/"><img src="https://img.shields.io/pypi/v/axm-git" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+" />
</p>

---

## What it does

`axm-git` provides deterministic, structured Git operations designed for AI agents. Instead of parsing raw `git` CLI output, agents get typed JSON responses with clear success/failure semantics and automatic retry on pre-commit hook fixes.

## Features

- 🔍 **Preflight** — Structured working tree status with diff summary
- 🌿 **Branch** — Create or checkout branches with one call
- 📦 **Commit** — Batched atomic commits with auto-retry on pre-commit fixes
- 🏷️ **Tag** — One-shot semver tagging from Conventional Commits
- 🚀 **Push** — Push with dirty-check, auto-upstream detection, and force support
- 🪝 **Hooks** — Lifecycle hook actions (preflight, create-branch, commit-phase, merge-squash) auto-discovered via entry-points

## Installation

```bash
uv add axm-git
```

## Quick Start

```python
# Check what changed
git_preflight(path="/path/to/repo")
# → {files: [{path: "foo.py", status: "M"}, ...], clean: false}

# Create or switch branch
git_branch(name="feat/new-feature", path="/path/to/repo")
# → {branch: "feat/new-feature"}

# Commit in batches
git_commit(path="/path/to/repo", commits=[
    {"files": ["src/foo.py"], "message": "feat: add foo"},
    {"files": ["tests/test_foo.py"], "message": "test: add foo tests"},
])

# Tag a release
git_tag(path="/path/to/repo")
# → {tag: "v0.2.0", bump: "minor", pushed: true}

# Push to remote
git_push(path="/path/to/repo")
# → {branch: "main", remote: "origin", pushed: true}
```

## Learn More

- [Getting Started Tutorial](tutorials/getting-started.md)
- [Architecture](explanation/architecture.md)
- [CLI Reference](reference/cli.md)
