# CLI Reference

## The `axm` Command

`axm` is a thin wrapper that autodiscovers commands from installed AXM packages.

```bash
axm              # list available commands (or show install hints)
axm <command>    # run a discovered command
axm --version    # print the installed axm version (also -V), exit 0
```

## Available Commands

Commands depend on which AXM packages are installed:

| Command | Package | Description |
|---|---|---|
| `axm init_scaffold` | `axm-init` | Scaffold a new project |
| `axm init_check` | `axm-init` | Check project conformity |
| `axm init_reserve` | `axm-init` | Reserve a PyPI package name |
| `axm audit` | `axm-audit` | Code quality audit |
| `axm-bib search` | `axm-bib` | Search papers |
| `axm-bib resolve` | `axm-bib` | Resolve a reference (DOI/arXiv/title) to BibTeX |
| `axm-bib pdf` | `axm-bib` | Download + extract paper PDFs |
| `axm-bib extract` | `axm-bib` | Extract local PDF to Markdown |
| `axm-mcp` | `axm-mcp` | MCP server exposing all AXM tools to AI agents |

## Non-scalar parameters

Each tool's CLI signature mirrors its `execute` signature exactly, including the
`Annotated[..., cyclopts.Parameter(...)]` convention. Non-scalar parameters
(`list` / `dict` / `tuple` / `set` / pydantic models), whether bare, wrapped in
`Optional` / `X | None`, or wrapped in `Annotated[...]`, are passed as a single
JSON string and decoded before the call:

```bash
axm batch_edit --path . --operations '[{"op": "replace", "file": "x.py"}]'
```

This keeps the tool signature and the CLI signature identical without
CLI-only flags. Invalid JSON exits with code `2` (a guard raised by the wrapper
itself).

Tool `execute` parameters are keyword-only by convention, but the CLI relaxes
them so **both** the positional form `axm audit .` and the keyword form
`axm audit --path .` work.

## Python API

::: axm.cli.create_app

::: axm.cli.build_command_for_tool

## Tool Interface

::: axm.tools.base.ToolResult

::: axm.tools.base.AXMTool

!!! tip "Agent hints"
    Tools can set an `agent_hint` class attribute (one-liner string) to provide
    LLM-optimized descriptions that propagate to MCP tool listings. It is a
    best-effort discovery attribute (read via `tool_metadata` / `getattr`), not
    a protocol member — when absent, nothing is substituted (there is no
    guaranteed docstring fallback).

## Hook Interface

::: axm.hooks.base.HookResult

::: axm.hooks.base.HookAction
