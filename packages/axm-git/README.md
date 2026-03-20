<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>axm-git — Deterministic Git workflows for AI agents</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-git/axm-audit.json" alt="axm-audit"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-git/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-git/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-git/"><img src="https://img.shields.io/pypi/v/axm-git" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://forge.axm-protocols.io/git/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

## Features

- 🔍 **Preflight** — Structured working tree status with diff summary
- 🌿 **Branch** — Create or checkout branches with one call
- 📦 **Commit** — Batched atomic commits with auto-retry on pre-commit fixes
- 🏷️ **Tag** — One-shot semver tagging from Conventional Commits
- 🚀 **Push** — Push with dirty-check, auto-upstream detection, and force support
- 🧭 **Error Recovery** — When called on a non-git directory, tools suggest nearby git repos
- 🪝 **Hooks** — Lifecycle hook actions (preflight, create-branch, commit-phase, merge-squash, worktree-add, worktree-remove) with `enabled` guard, auto-discovered via entry-points
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

# Create or switch branch
git_branch(name="feat/new-feature", path="/path/to/repo")
# → {branch: "feat/new-feature"}

# Commit in batches
git_commit(path="/path/to/repo", commits=[
    {"files": ["src/foo.py"], "message": "feat: add foo"},
    {"files": ["tests/test_foo.py"], "message": "test: add foo tests"},
])
# → {results: [{sha: "abc1234", precommit_passed: true}, ...]}

# Tag a release
git_tag(path="/path/to/repo")
# → {tag: "v0.2.0", bump: "minor", pushed: true}

# Push to remote
git_push(path="/path/to/repo")
# → {branch: "main", remote: "origin", pushed: true}
```

## MCP Tools

### `git_preflight`

Report working tree changes so the agent can plan commits.

| Parameter | Default | Description |
|---|---|---|
| `path` | `.` | Project root directory |
| `diff_lines` | `200` | Max diff lines to include (0 to disable) |

Returns: file list with status (`M`, `A`, `D`, `??`), diff stat, clean flag.

### `git_branch`

Create or checkout a git branch.

| Parameter | Default | Description |
|---|---|---|
| `name` | *required* | Branch name |
| `from_ref` | `None` | Ref to branch from (tag, commit, branch) |
| `checkout_only` | `False` | If `True`, checkout existing branch without creating |
| `path` | `.` | Project root directory |

Returns: `{branch: "<current branch>"}` on success.

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
| `version` | *auto* | Override the computed version (e.g. `"v1.0.0"`) |

Pipeline: clean tree check → CI status check → semver bump → annotate tag → hatch-vcs verify → push.

### `git_push`

Push the current branch to a remote after verifying a clean working tree.

| Parameter | Default | Description |
|---|---|---|
| `path` | `.` | Project root directory |
| `remote` | `origin` | Remote name |
| `set_upstream` | `True` | Auto-set upstream for new branches |
| `force` | `False` | Force-push |

Pipeline: repo check → dirty check → detect branch → detect upstream → push.

## Development

This package is part of the [**axm-forge**](https://github.com/axm-protocols/axm-forge) workspace.

```bash
git clone https://github.com/axm-protocols/axm-forge.git
cd axm-forge
uv sync --all-groups
uv run --package axm-git --directory packages/axm-git pytest -x -q
```

📖 **[Full documentation](https://forge.axm-protocols.io/git/)**

## License

Apache-2.0 — © 2026 axm-protocols
