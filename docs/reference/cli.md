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
| `axm-bib search` | `axm-bib` | Search papers |
| `axm-bib doi` | `axm-bib` | Resolve DOI to BibTeX |
| `axm-bib pdf` | `axm-bib` | Download + extract paper PDFs |
| `axm-bib extract` | `axm-bib` | Extract local PDF to Markdown |

## Python API

::: axm.cli.create_app

## Tool Interface

::: axm.tools.base.ToolResult

::: axm.tools.base.AXMTool
