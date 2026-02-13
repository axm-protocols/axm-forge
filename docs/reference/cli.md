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
| `axm init` | `axm-init` | Scaffold a new project |
| `axm check` | `axm-init` | Check project conformity |
| `axm audit` | `axm-audit` | Code quality audit |
| `axm search` | `axm-bib` | Search papers |
| `axm pdf` | `axm-bib` | Download paper PDFs |
| `axm run` | `axm-engine` | Run a protocol |
| `axm read` | `axm-engine` | Read a URI |

## Python API

::: axm.cli.create_app
