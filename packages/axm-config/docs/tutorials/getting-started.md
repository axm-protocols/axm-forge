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

## Step 3: Handle a misconfigured `HOME`

`axm-config` refuses a `~/.axm` that resolves inside a git checkout (a `HOME`
pointing into a repo, e.g. dotfiles managed under a `~/.git`). The refusal is a
typed `ConfigError` (`UnsafeHomeError`), so the CLI exits `1` with a one-line
error rather than a raw traceback, and `get`/`load` propagate a catchable
exception:

```bash
axm-config get demo key
# error: refusing in-repo path .../.axm: resolves inside the git checkout at ...
```

## Step 4: Run the Tests

The package has no local `Makefile`; run its suite from the workspace with `uv`:

```bash
uv run --package axm-config --directory packages/axm-config pytest -x -q
```

## Next Steps

- [CLI Reference](../reference/cli.md) — Full command documentation
- [Architecture](../explanation/architecture.md) — How the project is structured
