<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-init/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>axm-git — Deterministic Git workflow tools for AI agents</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-git/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-git/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/axm-protocols/axm-git/actions/workflows/axm-init.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-git/gh-pages/badges/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-git/actions/workflows/axm-audit.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-git/gh-pages/badges/axm-audit.json" alt="axm-audit"></a>
  <a href="https://coveralls.io/github/axm-protocols/axm-git?branch=main"><img src="https://coveralls.io/repos/github/axm-protocols/axm-git/badge.svg?branch=main" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-git/"><img src="https://img.shields.io/pypi/v/axm-git" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://axm-protocols.github.io/axm-git/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

## What it does

Replaces 9+ shell commands with **3 MCP tool calls** for Git operations:

| Tool | Purpose | Replaces |
|---|---|---|
| `git_preflight` | Working tree status + diff summary | `git status` + `git diff --stat` |
| `git_commit` | Batched atomic commits with pre-commit | `git add` + `git commit` × N |
| `git_tag` | Semver tag (preflight → compute → create → push) | 6+ commands |

## Features

- ✅ **Deleted file support** — `git add -A --` handles additions, modifications, and deletions
- ✅ **Auto-retry** — Re-stages and retries once when pre-commit hooks auto-fix files (e.g. ruff)
- ✅ **Conventional Commits** — Automatic semver bump from commit messages (`feat:` → minor, `fix:` → patch)
- ✅ **CI-aware tagging** — Checks GitHub Actions status before creating tags
- ✅ **hatch-vcs** — Verifies version sync when using hatch-vcs
- ✅ **99% test coverage** — 69 tests (unit + functional)

## Installation

```bash
uv add axm-git
```

## Usage (MCP)

Tools are auto-discovered via `axm.tools` entry points. Use them through the AXM MCP server:

```python
# Check working tree status
git_preflight(path="/path/to/repo")
# → {"success": true, "files": [...], "diff_stat": "...", "clean": false}

# Batch commits
git_commit(path="/path/to/repo", commits=[
    {"files": ["src/foo.py"], "message": "feat: add foo"},
    {"files": ["tests/test_foo.py"], "message": "test: add foo tests"},
])
# → {"success": true, "results": [{"sha": "abc1234", ...}], "total": 2}

# Create semver tag
git_tag(path="/path/to/repo")
# → {"success": true, "tag": "v0.2.0", "pushed": true}
```

## Architecture

```
src/axm_git/
├── core/
│   ├── runner.py      # run_git, run_gh, gh_available, detect_package_name
│   └── semver.py      # parse_tag, compute_bump, VersionBump
└── tools/
    ├── tag.py              # GitTagTool (AXMTool)
    ├── commit.py           # GitCommitTool (AXMTool)
    └── commit_preflight.py # GitPreflightTool (AXMTool)
```

## Development

```bash
git clone https://github.com/axm-protocols/axm-git.git
cd axm-git
uv sync --all-groups
make check
```

| Command | Description |
|---|---|
| `make check` | Run lint + test in one step |
| `make lint` | Lint with ruff + mypy |
| `make format` | Format with ruff |
| `make test` | Run pytest with coverage |
| `make docs-serve` | Preview docs locally |

## License

MIT — © 2026 axm-protocols
