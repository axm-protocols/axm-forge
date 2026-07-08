<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>AXM CLI — Unified command-line interface for the AXM ecosystem</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm/axm-audit.json" alt="axm-audit"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm/"><img src="https://img.shields.io/pypi/v/axm" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://forge.axm-protocols.io/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

## Features

- 🔌 **Autodiscovery** — automatically finds commands from installed AXM packages via entry points
- 🧩 **Modular** — install only what you need (`axm[init]`, `axm[audit]`, `axm[bib]`, `axm[mcp]`)
- 🛠️ **Shared interface** — re-exports the core contracts from the package root (`from axm import AXMTool, ToolResult, HookAction, HookResult, WitnessResult, ValidationFeedback, WitnessRule, tool_node, tool_metadata, ToolMetadata, ToolNodeError`): `AXMTool`/`ToolResult` (with optional `agent_hint` for LLM-optimized descriptions and `text` for pre-rendered output), `HookAction`/`HookResult`, `WitnessResult`/`ValidationFeedback`/`WitnessRule`, and `tool_node` (adapt any `axm.tools` tool into a DAG python-node) for ecosystem development
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

The `axm` CLI discovers these from entry-point metadata and dispatches lazily — it imports only the command you invoke, not every tool at startup.

## Package Structure

```
axm/
├── src/axm/
│   ├── cli.py            # Lazy, dispatch-first autodiscovery wrapper
│   ├── hooks/
│   │   ├── base.py       # HookAction Protocol + HookResult (lifecycle hooks)
│   │   └── __init__.py
│   ├── tools/
│   │   ├── base.py       # AXMTool Protocol + ToolResult + ToolMetadata
│   │   ├── node.py       # tool_node adapter + ToolNodeError (AXMTool → DAG node)
│   │   ├── _discovery.py # entry-point metadata helper
│   │   └── __init__.py
│   ├── witnesses.py      # WitnessResult + ValidationFeedback + WitnessRule
│   └── __init__.py
└── tests/
    ├── unit/             # mirrors src/ (hooks/, tools/, cli, witnesses, __init__)
    └── e2e/              # CLI invoked as a subprocess (test_axm.py)
```

## Development

This package is part of the **axm-forge** workspace.

```bash
git clone https://github.com/axm-protocols/axm-forge.git
cd axm-forge
uv sync --all-groups
uv run --package axm --directory packages/axm pytest
```

## License

Apache-2.0 — © 2026 Gabriel Jarry
