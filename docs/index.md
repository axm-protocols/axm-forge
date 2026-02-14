---
hide:
  - navigation
  - toc
---

# axm-git

<p align="center">
  <strong>Deterministic Git workflow tools for AI agents</strong>
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

## What it does

Consolidates 9+ shell commands into **3 MCP tool calls** for Git operations:

| Tool | Purpose |
|---|---|
| `git_preflight` | Working tree status and diff summary |
| `git_commit` | Batched atomic commits with pre-commit handling |
| `git_tag` | One-shot semver tagging (preflight → compute → create → push) |

## Installation

```bash
uv add axm-git
```

## Quick Start

Tools are auto-discovered via `axm.tools` entry points:

```python
from axm_git.tools.commit_preflight import GitPreflightTool

result = GitPreflightTool().execute(path="/path/to/repo")
print(result.data["files"])  # [{"path": "foo.py", "status": "M"}, ...]
```

---

<div style="text-align: center; margin: 2rem 0;">
  <a href="tutorials/getting-started/" class="md-button md-button--primary">Get Started →</a>
  <a href="reference/api/" class="md-button">API Reference</a>
</div>
