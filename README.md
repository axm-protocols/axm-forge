# axm

**AXM CLI — Unified command-line interface for the AXM ecosystem.**

<p align="center">
  <a href="https://github.com/axm-protocols/axm/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/axm/"><img src="https://img.shields.io/pypi/v/axm" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
</p>

---

## What is axm?

`axm` is a thin CLI wrapper that **autodiscovers commands** from installed AXM packages via entry points. Install only what you need:

```bash
pip install axm              # CLI shell only
pip install axm[init]        # + scaffolding & project checks
pip install axm[audit]       # + code quality audits
pip install axm[mcp]         # + MCP server
pip install axm[bib]         # + bibliography tools
pip install axm[all]         # everything
```

## Usage

```bash
axm                     # shows available commands
axm init my-project     # if axm-init is installed
axm audit .             # if axm-audit is installed
```

## How It Works

Each AXM package declares commands via `pyproject.toml`:

```toml
# axm-init/pyproject.toml
[project.entry-points."axm.commands"]
init = "axm_init.cli:init"
check = "axm_init.cli:check"
```

The `axm` CLI discovers these at startup and exposes them as subcommands.

## Package Structure

```
axm/
├── src/axm/
│   ├── cli.py         # Autodiscovery wrapper (~80 lines)
│   └── __init__.py
└── tests/
    └── test_cli.py
```

## Development

```bash
git clone https://github.com/axm-protocols/axm.git
cd axm
uv sync --all-groups
uv run pytest
```

## License

Apache License 2.0
