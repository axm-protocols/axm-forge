<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-init/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<h1 align="center">axm-forge</h1>
<p align="center"><strong>Developer tools for the AXM ecosystem.</strong></p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-audit.json" alt="axm-audit"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/coverage.json" alt="Coverage"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://forge.axm-protocols.io"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

## Philosophy

AXM Forge provides the **developer toolchain** for the AXM ecosystem. Every tool returns structured, deterministic results — designed for AI agents that need precise answers, not text to parse.

- 🌳 **AST-Powered Introspection** — Tree-sitter based analysis that understands Python at the structural level. Find callers, measure blast radius, and trace import graphs — all without grep noise.
- 🛡️ **Codified Quality Gates** — 40+ rules covering lint, types, coverage, complexity, security, and project governance — all in a single `verify()` call.
- 📦 **Automated Scaffolding** — Generate projects, workspaces, and workspace members that pass all 39 governance checks from day one.
- 🔀 **Git Workflow Automation** — Structured commits with auto-staging, pre-commit retry, and conventional commit enforcement. Semver tagging and push — all through agent-friendly MCP tools.

## Packages

| Package | Description | Version | Quality |
|---|---|---|---|
| [axm-ast](packages/axm-ast/) | AST introspection CLI for AI agents, powered by tree-sitter | [![PyPI](https://img.shields.io/pypi/v/axm-ast)](https://pypi.org/project/axm-ast/) | [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ast/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ast/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-audit](packages/axm-audit/) | Code auditing and quality rules for Python projects | [![PyPI](https://img.shields.io/pypi/v/axm-audit)](https://pypi.org/project/axm-audit/) | [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-audit/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-audit/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-init](packages/axm-init/) | Python project scaffolding CLI with Copier templates | [![PyPI](https://img.shields.io/pypi/v/axm-init)](https://pypi.org/project/axm-init/) | [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-init/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-init/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-git](packages/axm-git/) | Git workflow automation for AXM agents | [![PyPI](https://img.shields.io/pypi/v/axm-git)](https://pypi.org/project/axm-git/) | [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-git/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-git/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |

## Quick Start

```bash
# Clone and install
git clone https://github.com/axm-protocols/axm-forge.git
cd axm-forge
uv sync --all-groups

# Run all tests
make test-all

# Lint + type check
make lint

# Full quality gate
make check
```

## Architecture

```mermaid
graph TD
    classDef ast fill:#5C6BC0,stroke:#3949AB
    classDef audit fill:#42A5F5,stroke:#1E88E5
    classDef init fill:#26C6DA,stroke:#00ACC1
    classDef git fill:#78909C,stroke:#546E7A

    AST["axm-ast<br/>AST introspection"]:::ast
    AUDIT["axm-audit<br/>Code auditing"]:::audit --> AST
    INIT["axm-init<br/>Scaffolding"]:::init
    GIT["axm-git<br/>Git automation"]:::git
```

## Development

Each package is independently versioned with prefixed tags (`ast/v*`, `audit/v*`, `init/v*`, `git/v*`).

| Command | Description |
|---|---|
| `make test-all` | Run tests for all packages |
| `make lint` | Ruff + mypy for all packages |
| `make check` | Lint + tests |
| `make axm-audit` | Run axm-audit on each package |
| `make axm-init` | Run axm-init check on each package |
| `make quality` | Full AXM quality gate (pre-push) |
| `make docs-serve` | Preview documentation |

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
