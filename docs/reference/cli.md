# CLI Reference

## The `axm` Command

`axm` is a thin wrapper that autodiscovers commands from installed AXM packages.

```bash
axm              # list available commands (or show install hints)
axm <command>    # run a discovered command
```

## Available Commands

Commands depend on which AXM packages are installed:

| Command | Package | Description |
|---|---|---|
| `axm init_scaffold` | `axm-init` | Scaffold a new project |
| `axm init_check` | `axm-init` | Check project conformity |
| `axm init_reserve` | `axm-init` | Reserve a PyPI package name |
| `axm audit` | `axm-audit` | Code quality audit |
| `axm bib_search` | `axm-bib` | Search papers |
| `axm bib_pdf` | `axm-bib` | Download paper PDFs |
| `axm protocol_run` | `axm-engine` | Run a protocol |
| `axm protocol_read` | `axm-engine` | Read a URI |

## Python API

::: axm.cli.create_app

## Tool Interface

::: axm.tools.base.ToolResult

::: axm.tools.base.AXMTool
