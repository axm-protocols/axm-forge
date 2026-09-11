<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>axm-git — Deterministic Git workflows for AI agents</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-git/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-git/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-git/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-git/"><img src="https://img.shields.io/pypi/v/axm-git" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://forge.axm-protocols.io/axm-git/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

Git workflow automation for AXM agents: inspect changes, stage explicit files,
commit, manage branches and worktrees, and publish through Git and GitHub.

## Features

- Inspect repository status, diffs and package release history.
- Commit explicit file batches with identity resolution and partial-result reporting.
- Manage branches, worktrees, clones and local merges.
- Push changes, create pull requests, publish tags and observe GitHub merge status.

## Installation

Python 3.12+ and Git are required. GitHub operations also need the `gh` CLI
and an authenticated session. In a Python project managed by uv:

```bash
uv add axm-git
```

## Quick Start

From an existing Git repository, use the installed project environment:

```bash
uv run axm git_preflight --path . --diff-lines 0
```

This command reads the current repository and reports changed files and a
diff summary without patch content. A package subdirectory limits preflight's
status and diff scope; use the repository root for a repository-wide check.
It does not stage, commit or publish anything.

## Usage

### CLI and MCP

The `axm` CLI and MCP use the same tools registered under `axm.tools`.
There is no separate `axm-git` executable. See the
[CLI and MCP guide](docs/howto/mcp.md) and
[complete tool contracts](docs/reference/cli.md).

| Operation | Tools | Effects |
|---|---|---|
| Inspect locally | `git_preflight`, `git_release_diff`, `git_worktree(action="list")` | Read repository state |
| Change locally | `git_branch`, `git_commit`, `git_merge`, worktree add/remove | Change branches, index, files or commits |
| Obtain remote content | `git_clone`, `git_pull` | Read remote; write local checkout |
| Publish | `git_push`, `git_pr`, `git_tag` | Change remote state |
| Observe GitHub | `git_await_merge` | Poll a PR; does not merge it |

### Commit and release boundaries

`git_commit` processes a batch sequentially: earlier successful commits remain
if a later item fails. It stages declared paths, refuses unrelated staged
paths, and retries once on the commit-hook “files were modified” marker.
[Commit recovery](docs/howto/commits.md) explains partial results and hook
observations.

**`git_tag` creates an annotated local tag and pushes it to origin.** It has
no list, preview, dry-run or local-only mode. Use `git_release_diff` for
read-only release analysis. The tag CI guard blocks only `red`, not
`pending`, `error` or `skipped`.
[Release guide](docs/howto/releases.md) describes the current limitations.

## Documentation

- [Read-only tutorial](docs/tutorials/getting-started.md)
- [Task guides](docs/howto/index.md)
- [Tool contracts](docs/reference/cli.md)
- [Architecture](docs/explanation/architecture.md)
- [Published documentation](https://forge.axm-protocols.io/axm-git/)

The site homepage is [docs/index.md](docs/index.md); this README is the repository
entry point. Generated API documentation includes internal modules; generation
does not make every Python symbol a public root export.

## Development

Development takes place in the [axm-forge workspace](https://github.com/axm-protocols/axm-forge).

```bash
git clone https://github.com/axm-protocols/axm-forge.git
cd axm-forge
uv sync --all-packages --all-groups
uv run --package axm-git --directory packages/axm-git pytest
```

Tests live in `tests_axm_git/`. From `packages/axm-git`, build the package
documentation with `mkdocs build --strict` in an environment containing its
docs dependencies.

## License

Licensed under Apache-2.0. See [LICENSE](LICENSE).
