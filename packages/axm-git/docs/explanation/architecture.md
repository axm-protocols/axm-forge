# Architecture

## Overview

`axm-git` provides deterministic MCP tools that wrap Git and GitHub CLI operations. Each tool satisfies the `AXMTool` protocol (from `axm`) and is auto-discovered via Python entry points.

```mermaid
graph TD
    subgraph "MCP Layer"
        MCP["axm-mcp server"]
    end

    subgraph "Tools"
        Tag["GitTagTool"]
        Commit["GitCommitTool"]
        Preflight["GitPreflightTool"]
        Branch["GitBranchTool"]
        Push["GitPushTool"]
    end

    subgraph "Hooks"
        PF["PreflightHook"]
        CB["CreateBranchHook"]
        BD["BranchDeleteHook"]
        CP["CommitPhaseHook"]
        MS["MergeSquashHook"]
        WA["WorktreeAddHook"]
        WR["WorktreeRemoveHook"]
    end

    subgraph "Core"
        Runner["runner.py"]
        Semver["semver.py"]
        PhaseCommit["phase_commit.py"]
    end

    subgraph "External"
        Git["git CLI"]
        GH["gh CLI"]
    end

    subgraph "axm"
        HookBase["hooks.base<br>HookAction / HookResult"]
    end

    subgraph "axm-engine"
        Registry["HookRegistry"]
    end

    MCP --> Tag
    MCP --> Commit
    MCP --> Preflight
    MCP --> Branch
    MCP --> Push
    Tag --> Runner
    Tag --> Semver
    Commit --> Runner
    Preflight --> Runner
    Branch --> Runner
    Push --> Runner
    PF --> Runner
    CB --> Runner
    CP --> Runner
    CP --> PhaseCommit
    MS --> Runner
    WA --> Runner
    WR --> Runner
    BD --> Runner
    Runner --> Git
    Runner --> GH
    PF -.-> HookBase
    CB -.-> HookBase
    CP -.-> HookBase
    MS -.-> HookBase
    WA -.-> HookBase
    WR -.-> HookBase
    BD -.-> HookBase
    Registry -.->|"entry-point discovery"| PF
    Registry -.-> CB
    Registry -.-> CP
    Registry -.-> MS
    Registry -.-> WA
    Registry -.-> WR
    Registry -.-> BD
```

## Layers

### 1. Tools (`tools/`)

Each tool exposes an `execute(*, path, ..., **kwargs) → ToolResult` method with explicit typed parameters:

- **`GitTagTool`** — Full tag workflow: check clean tree, check CI, compute semver bump, create tag, verify hatch-vcs, push.
- **`GitCommitTool`** — Stage files, commit with pre-commit hooks, auto-retry on linter fixes. Supports batched commits.
- **`GitPreflightTool`** — Parse `git status --porcelain` and `git diff --stat` into structured data.
- **`GitBranchTool`** — Create or checkout a branch. Supports `from_ref` (branch from tag/commit) and `checkout_only` (switch without creating).
- **`GitPushTool`** — Push with dirty-check guard, auto-upstream detection, custom remote, and force-push support.

### 2. Core (`core/`)

Shared logic used by multiple tools:

- **`runner.py`** — `find_git_root()` locates the repository root via `rev-parse --show-toplevel`, `run_git()` and `run_gh()` subprocess wrappers, `gh_available()` auth check, `detect_package_name()` from `pyproject.toml`. Also provides `suggest_git_repos()` (scans for child directories that are git repos) and `not_a_repo_error()` (enriches "not a git repository" errors with suggestions for nearby repos).
- **`semver.py`** — `parse_tag()` for version parsing, `compute_bump()` for Conventional Commits analysis (returns `VersionBump` with next version + reason).
- **`phase_commit.py`** — `get_phase_commit()` looks up the commit hash for a given protocol phase name by searching git log.

### 3. Hooks (`hooks/`)

Lifecycle hook actions conforming to the `HookAction` protocol from `axm.hooks.base`. Auto-discovered via `axm.hooks` entry-points.

All hooks accept an `enabled` param (default `True`). Pass `enabled=False` to skip git operations entirely (returns `HookResult.ok(skipped=True, reason="git disabled")`).

- **`PreflightHook`** — Runs a structured working tree status check before a phase begins. Entry point: `git:preflight`.
- **`CreateBranchHook`** — Creates a session branch. Accepts `branch`, `ticket_id`, `ticket_title`, and `ticket_labels` params; `_resolve_branch()` derives the final branch name from those inputs. Skips if not a git repo.
- **`BranchDeleteHook`** — Deletes a branch via `git branch -D`. Branch name resolved from `branch` param then `branch` context key. Entry point: `git:branch-delete`.
- **`CommitPhaseHook`** — Stages all changes, commits with `[axm] {phase_name}`. Pass `from_outputs=True` to derive staged files from protocol outputs instead of staging everything. Skips if nothing to commit.
- **`MergeSquashHook`** — Squash-merges a branch back to the target branch. Accepts `branch` and `message` params; `_resolve_branch()` reads the branch from context when `branch` is not explicitly supplied.
- **`WorktreeAddHook`** — Creates a git worktree + branch for a ticket at `<repo_parent>/<ticket_id>/`, deriving the branch name from ticket metadata. Entry point: `git:worktree-add`.
- **`WorktreeRemoveHook`** — Removes a worktree previously created by `WorktreeAddHook` using `git worktree remove --force`. Entry point: `git:worktree-remove`.

## Design Decisions

| Decision | Rationale |
|---|---|
| `AXMTool` protocol | Consistent interface, auto-discovery via entry points |
| `subprocess` over `gitpython` | Zero dependency, deterministic, same behavior as manual CLI |
| Auto-retry on pre-commit fix | Agents waste a tool call without it |
| `git add -A --` | Handles additions, modifications, AND deletions in one command |
| Soft CI check | `gh` is optional — tagging still works without GitHub CLI |
