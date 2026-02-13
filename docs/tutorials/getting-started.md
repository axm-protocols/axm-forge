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
axm init_scaffold my-project  # scaffold a new project
axm init_check .              # check project conformity
axm audit .                   # run quality checks
```

## Step 2: Optional Dependencies

| Extra | Provides | Commands |
|---|---|---|
| `init` | `axm-init` | `axm init_scaffold`, `axm init_check`, `axm init_reserve` |
| `audit` | `axm-audit` | `axm audit` |
| `bib` | `axm-bib` | `axm-bib search`, `axm-bib pdf`, `axm-bib doi` |
| `all` | Everything above | All commands |

## Next Steps

- [Architecture](../explanation/architecture.md) — How autodiscovery works
- [Add a Command](../howto/index.md) — Register your own CLI command
