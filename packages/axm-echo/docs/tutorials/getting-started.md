# Getting Started

This tutorial walks you through installing `axm-echo` and verifying your setup.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

```bash
uv add axm-echo
```

Or with pip:

```bash
pip install axm-echo
```

To enable the optional neural backend (`torch` + `sentence-transformers`):

```bash
uv add "axm-echo[neural]"   # or: pip install "axm-echo[neural]"
```

## Step 1: Verify Installation

```python
from axm_echo import __version__

print(f"axm-echo v{__version__}")
```

## Step 2: Run the Tests

```bash
cd packages/axm-echo
make check
```

This runs lint + type check + security audit + tests.

## Next Steps

- [CLI Reference](../reference/cli.md) — Full command documentation
- [Architecture](../explanation/architecture.md) — How the project is structured
