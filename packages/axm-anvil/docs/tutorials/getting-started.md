# Getting Started

This tutorial walks you through installing `axm-anvil` and verifying your setup.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

```bash
uv add axm-anvil
```

Or with pip:

```bash
pip install axm-anvil
```

## Step 1: Verify Installation

```python
from axm_anvil import __version__

print(f"axm-anvil v{__version__}")
```

## Step 2: Run the Tests

```bash
cd packages/axm-anvil
make check
```

This runs lint + type check + security audit + tests.

## Next Steps

- [CLI Reference](../reference/cli.md) — Full command documentation
- [Architecture](../explanation/architecture.md) — How the project is structured
