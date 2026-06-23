# Getting Started

This tutorial walks you through installing `axm-config` and verifying your setup.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

```bash
uv add axm-config
```

Or with pip:

```bash
pip install axm-config
```

## Step 1: Verify Installation

```python
from axm_config import __version__

print(f"axm-config v{__version__}")
```

## Step 2: Resolve Config from the Shell

The `axm-config` command persists and resolves runtime config under `~/.axm`:

```bash
axm-config set research.fred api_key abc123  # writes [research.fred] in ~/.axm/config.toml
axm-config get research.fred api_key         # -> abc123
axm-config path                              # -> /Users/you/.axm
axm-config doctor research.fred              # -> research.fred.api_key: file
```

An environment variable always wins over the file value. The env name is
`AXM_<NS>_<KEY>` upper-cased, with each namespace dot folded to a *double*
underscore (so `research.fred` → `RESEARCH__FRED`):

```bash
AXM_RESEARCH__FRED_API_KEY=from-env axm-config get research.fred api_key  # -> from-env
```

## Step 3: Run the Tests

```bash
cd packages/axm-config
make check
```

This runs lint + type check + security audit + tests.

## Next Steps

- [CLI Reference](../reference/cli.md) — Full command documentation
- [Architecture](../explanation/architecture.md) — How the project is structured
