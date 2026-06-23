# Getting Started

This tutorial walks you through installing `axm-doctor` and verifying your setup.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

```bash
uv add axm-doctor
```

Or with pip:

```bash
pip install axm-doctor
```

## Step 1: Verify Installation

```python
from axm_doctor import __version__

print(f"axm-doctor v{__version__}")
```

## Step 2: Run the Tests

```bash
cd packages/axm-doctor
make check
```

This runs lint + type check + security audit + tests.

## Next Steps

- [CLI Reference](../reference/cli.md) — Full command documentation
- [Architecture](../explanation/architecture.md) — How the project is structured
