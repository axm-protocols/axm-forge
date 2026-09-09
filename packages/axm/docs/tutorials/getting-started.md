# Getting started

This tutorial installs the launcher and one provider, then inspects an available
command without creating files or publishing anything.

## Prerequisites

Use Python 3.12 or newer and uv. Start in an existing Python project.
If you do not have a project yet, create an empty one first:

```bash
uv init axm-demo
cd axm-demo
```

## Install a provider

```bash
uv add 'axm[init]'
uv run axm --version
uv run axm --help
```

The version is that of the installed `axm` distribution, not of every provider.
The catalog lists commands from the current environment. Installing `axm`
alone supplies SDK types and the launcher but no domain commands.

With pip, activate a virtual environment and use `pip install 'axm[init]'`;
then invoke `axm` directly instead of `uv run axm`.

## Inspect a command

```bash
uv run axm init_check --help
```

The help describes the installed provider's actual options. To check the project:

```bash
uv run axm init_check --path . --json-output
```

This is a real conformity check, so a new project may return a nonzero exit
status. The JSON is the tool's data mapping; check the exit status separately.
The launcher does not turn a failed check into success merely because it
produced JSON.

## Choose optional packages

| Extra | Installs |
|---|---|
| `init` | `axm-init` |
| `audit` | `axm-audit` |
| `bib` | `axm-bib` |
| `mcp` | `axm-mcp` |
| `all` | The four packages above |

Providers may expose additional standalone binaries. Their individual
documentation owns those contracts; the `axm` catalog lists entry-point names.

Continue with [writing a tool](../howto/write-tool.md) or consult
[CLI output and errors](../reference/cli.md).
