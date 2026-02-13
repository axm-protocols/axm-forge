# Getting Started

This tutorial walks you through installing `axm` and running your first command.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

Install the CLI with the plugins you need:

=== "Minimal"

    ```bash
    pip install axm
    ```

=== "With init & audit"

    ```bash
    pip install axm[init,audit]
    ```

=== "Everything"

    ```bash
    pip install axm[all]
    ```

## Step 1: Check Available Commands

```bash
axm
```

Without any plugins, `axm` will show which packages you can install. With plugins:

```bash
axm init my-project     # scaffold a new project
axm audit .             # run quality checks
```

## Step 2: Optional Dependencies

| Extra | Provides | Commands |
|---|---|---|
| `init` | `axm-init` | `axm init`, `axm check` |
| `audit` | `axm-audit` | `axm audit` |
| `mcp` | `axm-mcp` | MCP server |
| `bib` | `axm-bib` | `axm search`, `axm pdf` |
| `engine` | `axm-engine` | `axm run`, `axm read` |
| `all` | Everything | All commands |

## Next Steps

- [Architecture](../explanation/architecture.md) — How autodiscovery works
- [Add a Command](../howto/index.md) — Register your own CLI command
