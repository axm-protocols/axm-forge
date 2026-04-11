<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="140" />
</p>

<h1 align="center">axm (CLI)</h1>
<p align="center"><strong>Unified command-line interface for the AXM ecosystem.</strong></p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-nexus/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-nexus/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/axm-protocols/axm-nexus/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-nexus/gh-pages/badges/axm/axm-audit.json" alt="axm-audit"></a>
  <a href="https://github.com/axm-protocols/axm-nexus/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-nexus/gh-pages/badges/axm/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm/"><img src="https://img.shields.io/pypi/v/axm" alt="PyPI"></a>
</p>

---

## Features

- 🔌 **Autodiscovery** — automatically finds commands from installed AXM packages via entry points
- 🧩 **Modular** — install only what you need (`axm[init]`, `axm[audit]`, `axm[bib]`, `axm[mcp]`)
- 🛠️ **Shared interface** — provides `AXMTool`/`ToolResult` (with `text` for pre-rendered output), `HookAction`/`HookResult`, and `WitnessResult`/`WitnessRule` for ecosystem development
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
│   │   └── base.py    # HookAction Protocol + HookResult
│   ├── tools/
│   │   └── base.py    # AXMTool Protocol + ToolResult
│   └── witnesses.py   # WitnessResult + ValidationFeedback + WitnessRule
└── tests/
```

## Learn More

- [Getting Started Tutorial](tutorials/getting-started.md)
- [Architecture](explanation/architecture.md)
- [CLI Reference](reference/cli.md)
