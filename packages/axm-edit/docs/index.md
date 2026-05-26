# axm-edit

<p align="center">
  <strong>Atomic batch file editing for AI agents — replace, create, and delete files in a single MCP tool call</strong>
</p>

<p align="center">
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-draft-workspace/gh-pages/badges/axm-edit/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-draft-workspace/gh-pages/badges/axm-edit/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-draft-workspace/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-draft-workspace/gh-pages/badges/axm-edit/coverage.json" alt="Coverage"></a>
</p>

---

## What it does

IDE agents edit files one-at-a-time. A refactor touching 30 files = 30 tool calls — 70 % of the agent's budget goes to mechanics. `axm-edit` replaces all of that with **1 call**: a validated, atomic batch operation with git checkpoint rollback.

## Features

- :material-file-edit-outline: **`batch_edit`** — Replace, create, and delete files in a single atomic operation with automatic ruff --fix
- :material-book-open-variant: **`read_file`** — Read file content with optional line-range support
- :material-file-search-outline: **`search_files`** — Grep-like search across project files (literal or regex)
- :material-folder-outline: **`list_dir`** — List files and directories with metadata (recursive, depth-limited)
- :material-console: **`run_command`** — Execute shell commands with timeout and output truncation
- :material-undo: **`batch_rollback`** — Restore project state to a checkpoint via git stash
- :material-shield-check-outline: **Atomic** — All-or-nothing: validation runs before any file is touched
- :material-sort-descending: **Bottom-to-top** — Line edits applied in reverse order to avoid line-shift problems

## Modules

| Module | What it provides |
|---|---|
| [`axm_edit.core.engine`](reference/api/axm_edit/core/engine/) | `batch_apply` — validate-then-apply batch engine |
| [`axm_edit.core.checkpoint`](reference/api/axm_edit/core/checkpoint/) | `create_checkpoint` / `rollback` — git stash safety net |
| [`axm_edit.models.operations`](reference/api/axm_edit/models/operations/) | `Edit`, `ReplaceOp`, `CreateOp`, `DeleteOp`, `BatchResult` (incl. `lint_errors`) — Pydantic models |
| [`axm_edit.services.lint`](reference/api/axm_edit/services/lint/) | `claude_fix` — Claude subprocess auto-fix for remaining ruff errors (JSON old/new edit format) |
| [`axm_edit.services.lint_diff`](reference/api/axm_edit/services/lint_diff/) | `compute_lint_diffs`, `extract_rules_by_file` — tagged plus/minus diffs between post-agent and post-lint snapshots |
| [`axm_edit.tools`](reference/api/axm_edit/tools/) | MCP tools: `BatchEditTool`, `ReadFileTool`, `SearchFilesTool`, `RunCommandTool`, `BatchRollbackTool` |

## Learn More

- [Getting Started](tutorials/getting-started.md) — Install and use all tools in 5 minutes
- [How-To Guides](howto/index.md) — Task-oriented recipes
- [API Reference](reference/) — Full module documentation
- [Architecture](explanation/architecture.md) — Design decisions and module layout

::: axm_edit
