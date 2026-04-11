<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>AXM CLI — Unified command-line interface for the AXM ecosystem</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-nexus/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-nexus/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/axm-protocols/axm-nexus/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-nexus/gh-pages/badges/axm/axm-audit.json" alt="axm-audit"></a>
  <a href="https://github.com/axm-protocols/axm-nexus/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-nexus/gh-pages/badges/axm/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm/"><img src="https://img.shields.io/pypi/v/axm" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://nexus.axm-protocols.io/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

## Features

- 🔌 **Autodiscovery** — automatically finds commands from installed AXM packages via entry points
- 🧩 **Modular** — install only what you need (`axm[init]`, `axm[audit]`, `axm[bib]`, `axm[mcp]`)
- 🛠️ **Shared interface** — provides `AXMTool`/`ToolResult` (with optional `agent_hint` for LLM-optimized descriptions and `text` for pre-rendered output), `HookAction`/`HookResult`, and `WitnessResult`/`WitnessRule` for ecosystem development
- 📦 **Minimal** — only depends on `cyclopts`, everything else is optional

## Installation

```bash
uv add axm              # CLI shell only
uv add axm[init]        # + scaffolding & project checks
uv add axm[audit]       # + code quality audits
uv add axm[bib]         # + bibliography tools
uv add axm[mcp]         # + MCP server (for AI agents)
uv add axm[all]         # everything
```

<details>
<summary>Or with pip</summary>

```bash
pip install axm              # CLI shell only
pip install axm[init]        # + scaffolding & project checks
pip install axm[audit]       # + code quality audits
pip install axm[bib]         # + bibliography tools
pip install axm[mcp]         # + MCP server (for AI agents)
pip install axm[all]         # everything
```

</details>

## Usage

```bash
axm                          # shows available commands
axm init_scaffold my-project # if axm-init is installed
axm init_check .             # check project conformity
axm audit .                  # if axm-audit is installed
```

## How It Works

Each AXM package declares commands via `pyproject.toml`:

```toml
# axm-init/pyproject.toml
[project.entry-points."axm.commands"]
init_scaffold = "axm_init.cli:scaffold"
init_check    = "axm_init.cli:check"
init_reserve  = "axm_init.cli:reserve"
```

The `axm` CLI discovers these at startup and exposes them as subcommands.

## Package Structure

```
axm/
├── src/axm/
│   ├── cli.py         # Autodiscovery wrapper (~80 lines)
│   ├── hooks/
│   │   ├── base.py    # HookAction Protocol + HookResult (lifecycle hooks)
│   │   └── __init__.py
│   ├── tools/
│   │   ├── base.py    # AXMTool Protocol + ToolResult (shared interface)
│   │   └── __init__.py
│   ├── witnesses.py   # WitnessResult + ValidationFeedback + WitnessRule
│   └── __init__.py
└── tests/
    ├── hooks/
    │   └── test_base.py
    ├── tools/
    │   └── test_base.py
    ├── test_cli.py
    └── test_version.py
```

## Development

This package is part of the **axm-nexus** workspace.

```bash
git clone https://github.com/axm-protocols/axm-nexus.git
cd axm-nexus
uv sync --all-groups
uv run --package axm --directory packages/axm pytest
```

## License

Apache-2.0 — © 2026 Gabriel Jarry
