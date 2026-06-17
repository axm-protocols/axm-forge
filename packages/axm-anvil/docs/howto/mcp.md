# Use via MCP

`axm-anvil` exposes its CLI commands as MCP (Model Context Protocol) tools via `axm-mcp`. AI agents can call them directly without spawning subprocesses.

!!! info "Setup"
    These tools are served by `axm-mcp`. If you haven't connected the server yet,
    see the **[axm-mcp Quick Start](https://forge.axm-protocols.io/mcp/tutorials/quickstart/)** —
    one command connects the whole toolchain. No per-package install needed.

## Available Tools

| MCP Tool | Purpose |
|---|---|
| `ast_move` | Deterministic CST-based refactor: move top-level symbols (classes, functions, constants) between Python modules, repairing every import and caller reference atomically |
| `ast_rename` | Deterministic CST-based refactor: rename top-level symbols in place (definition + internal usages) and rewrite every cross-file caller (`from mod import Old` imports and usages) atomically |

## Usage

!!! note "MCP dispatch"
    The example below shows the **logical API** — the parameters the tool takes.
    In practice, AI agents call this via MCP tool dispatch (e.g. `mcp_axm-mcp_ast_move`),
    not direct Python imports.

`ast_move` moves the named `symbols` from `from_file` to `to_file`, copying transitively-referenced imports, constants, and local helpers, then rewriting every `from old_module import …` caller line to point at the new module. All edits are computed in memory, validated, and written all-or-nothing.

```
ast_move(
    from_file="src/mylib/models.py",
    to_file="src/mylib/services.py",
    symbols="UserService,_validate_input",
    path="/project",
    dry_run=True,
)
```

Useful options (full list in the [CLI Reference](../reference/cli.md)):

- `dry_run=True` — preview the plan without writing files
- `check=True` — simulate the move with import-cycle detection (fails on a new cycle)
- `strict=True` — fail on an absent symbol instead of skipping it with a warning
- `rename='{"OldName": "NewName"}'` — rename moved definitions and rewrite all references
- `reexport=True` — leave callers untouched and inject a backwards-compat re-export
- `insert_after="<symbol>"` — splice moved blocks after a named target symbol

The result is a `ToolResult` carrying the move plan (moved symbols, copied imports/constants, updated callers, and any warnings).

### `ast_rename`

`ast_rename` renames the symbols in `mapping` (or the single `old`→`new`
pair) **in place** in `file`: it rewrites the definition and every internal
usage, then rewrites each cross-file caller — the `from mod import Old`
import alias and every usage of the renamed name. Unlike `ast_move` no block
is copied between files; the symbol keeps its module. All edits are computed
in memory, validated, and written all-or-nothing.

```
ast_rename(
    file="src/mylib/models.py",
    old="OldName",
    new="NewName",
    path="/project",
    dry_run=True,
)
```

Useful options:

- `old` / `new` — mono-symbol rename (ergonomic single case)
- `mapping='{"Old": "New"}'` — batch rename of several symbols in one call
- `dry_run=True` — preview the plan without writing files
- `strict=True` — fail (`success=False`) on an absent symbol instead of skipping it with a warning

The result is a `ToolResult` carrying the rename plan (`renamed`,
`callers_updated`, `warnings`, `files_modified`). Caller rewriting is
pattern-based on imports; shadowing, alias chains, and re-exports/star
imports are out of scope (deferred to a later tier).

## Other Refactorings

`axm-anvil` also performs split and merge refactorings. These are available
through the [`axm-anvil` CLI](../reference/cli.md); `ast_move` and
`ast_rename` are the operations surfaced as MCP tools.

## Entry Points

`ast_move` and `ast_rename` are auto-discovered via the `axm.tools`
entry-point group (`ast_move = "axm_anvil.tools.move:MoveTool"`,
`ast_rename = "axm_anvil.tools.rename:RenameTool"`). `axm-mcp` picks them up
automatically at startup.
