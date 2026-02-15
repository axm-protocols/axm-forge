# Architecture

## Overview

`axm-git` provides deterministic MCP tools that wrap Git and GitHub CLI operations. Each tool is a subclass of `AXMTool` (from `axm-core`) and is auto-discovered via Python entry points.

```mermaid
graph TD
    subgraph "MCP Layer"
        MCP["axm-mcp server"]
    end

    subgraph "Tools"
        Tag["GitTagTool"]
        Commit["GitCommitTool"]
        Preflight["GitPreflightTool"]
    end

    subgraph "Hooks"
        CB["CreateBranchHook"]
        CP["CommitPhaseHook"]
        MS["MergeSquashHook"]
    end

    subgraph "Core"
        Runner["runner.py"]
        Semver["semver.py"]
    end

    subgraph "External"
        Git["git CLI"]
        GH["gh CLI"]
    end

    subgraph "axm-engine"
        Registry["HookRegistry"]
    end

    MCP --> Tag
    MCP --> Commit
    MCP --> Preflight
    Tag --> Runner
    Tag --> Semver
    Commit --> Runner
    Preflight --> Runner
    CB --> Runner
    CP --> Runner
    MS --> Runner
    Runner --> Git
    Runner --> GH
    Registry -.->|"entry-point discovery"| CB
    Registry -.-> CP
    Registry -.-> MS
```

## Layers

### 1. Tools (`tools/`)

Each tool exposes a single `execute(**kwargs) → ToolResult` method:

- **`GitTagTool`** — Full tag workflow: check clean tree, check CI, compute semver bump, create tag, verify hatch-vcs, push.
- **`GitCommitTool`** — Stage files, commit with pre-commit hooks, auto-retry on linter fixes. Supports batched commits.
- **`GitPreflightTool`** — Parse `git status --porcelain` and `git diff --stat` into structured data.

### 2. Core (`core/`)

Shared logic used by multiple tools:

- **`runner.py`** — `run_git()` and `run_gh()` subprocess wrappers, `gh_available()` auth check, `detect_package_name()` from `pyproject.toml`.
- **`semver.py`** — `parse_tag()` for version parsing, `compute_bump()` for Conventional Commits analysis (returns `VersionBump` with next version + reason).

### 3. Hooks (`hooks/`)

Lifecycle hook actions conforming to the `HookAction` protocol from `axm-engine`. Auto-discovered via `axm.hooks` entry-points:

- **`CreateBranchHook`** — Creates a session branch `{prefix}/{session_id}`. Skips if not a git repo.
- **`CommitPhaseHook`** — Stages all changes, commits with `[axm] {phase_name}`. Skips if nothing to commit.
- **`MergeSquashHook`** — Squash-merges the session branch back to the target branch.

## Design Decisions

| Decision | Rationale |
|---|---|
| `AXMTool` subclass | Consistent interface, auto-discovery via entry points |
| `subprocess` over `gitpython` | Zero dependency, deterministic, same behavior as manual CLI |
| Auto-retry on pre-commit fix | Agents waste a tool call without it |
| `git add -A --` | Handles additions, modifications, AND deletions in one command |
| Soft CI check | `gh` is optional — tagging still works without GitHub CLI |
