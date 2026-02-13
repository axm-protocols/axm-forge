# Getting Started

This tutorial walks you through installing `axm` and running your first command.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

```bash
uv add axm
```

Or with pip:

```bash
pip install axm
```

## Step 1: Import and Use

```python
from axm import hello

print(hello())
# Output: Hello from axm!
```

## Step 2: Run the Tests

```bash
cd axm
make check
```

This runs lint + type check + security audit + tests.

## Next Steps

- [CLI Reference](../reference/cli.md) — Full command documentation
- [Architecture](../explanation/architecture.md) — How the project is structured
