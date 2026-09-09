# Getting Started

This tutorial walks you through installing `axm-init` and verifying your setup.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

```bash
uv tool install --with axm-init axm
```

Check that the tool is discoverable:

```bash
axm init_scaffold --help
```

Inside an existing uv project, use `uv add axm-init` and `uv run axm ...`.

## Quick Start

See the [Quickstart](quickstart.md) guide for a hands-on tutorial.

## Next Steps

- [CLI Reference](../reference/cli.md) — Full command documentation
- [Architecture](../explanation/architecture.md) — How the project is structured
