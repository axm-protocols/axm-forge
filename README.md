<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-init/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>axm-git — Deterministic Git workflows for AI agents</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-git/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-git/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://axm-protocols.github.io/axm-init/explanation/check-grades/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-git/gh-pages/badges/axm-init.json" alt="axm-init"></a>
  <a href="https://axm-protocols.github.io/axm-audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-git/gh-pages/badges/axm-audit.json" alt="axm-audit"></a>
  <a href="https://coveralls.io/github/axm-protocols/axm-git?branch=main"><img src="https://coveralls.io/repos/github/axm-protocols/axm-git/badge.svg?branch=main" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-git/"><img src="https://img.shields.io/pypi/v/axm-git" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://axm-protocols.github.io/axm-git/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

## Features

- 🔍 **Preflight** — Structured working tree status with diff summary
- 📦 **Commit** — Batched atomic commits with auto-retry on pre-commit fixes
- 🏷️ **Tag** — One-shot semver tagging from Conventional Commits
- 🪝 **Hooks** — Lifecycle hook actions (create-branch, commit-phase, merge-squash) with `enabled` guard, auto-discovered via entry-points
- 🔎 **Phase Lookup** — `get_phase_commit()` retrieves commit hashes for protocol phases

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
# → {results: [{sha: "abc1234", precommit_passed: true}, ...]}

# Tag a release
git_tag(path="/path/to/repo")
# → {tag: "v0.2.0", bump: "minor", pushed: true}
```

## MCP Tools

### `git_preflight`

Report working tree changes so the agent can plan commits.

| Parameter | Default | Description |
|---|---|---|
| `path` | `.` | Project root directory |

Returns: file list with status (`M`, `A`, `D`, `??`), diff stat, clean flag.

### `git_commit`

Execute one or more atomic commits with pre-commit hook handling.

| Parameter | Default | Description |
|---|---|---|
| `path` | `.` | Project root directory |
| `commits` | *required* | List of commit specs (see below) |

Each commit spec:

| Field | Required | Description |
|---|---|---|
| `files` | ✅ | Files to stage |
| `message` | ✅ | Commit summary (Conventional Commits) |
| `body` | | Extended commit body |

When a pre-commit hook auto-fixes files (e.g. ruff `--fix`), the tool re-stages and retries once automatically.

### `git_tag`

Compute the next semver version from Conventional Commits, create and push the tag.

| Parameter | Default | Description |
|---|---|---|
| `path` | `.` | Project root directory |
| `version` | *auto* | Override the computed version |
| `push` | `true` | Push tag to remote |

Pipeline: clean tree check → CI status check → semver bump → annotate tag → hatch-vcs verify → push.

## Development

```bash
git clone https://github.com/axm-protocols/axm-git.git
cd axm-git
uv sync --all-groups
uv run pytest           # 88 tests
uv run ruff check src/  # lint
```

## License

Apache License 2.0
