<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-init/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<h1 align="center">axm-forge</h1>
<p align="center"><strong>Developer tools for the AXM ecosystem.</strong></p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io"><img src="https://img.shields.io/badge/docs-forge.axm--protocols.io-blue" alt="Docs"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/license-Apache%202.0-green" alt="License">
</p>

---

## Packages

| Package | Description | Version |
|---|---|---|
| **axm-ast** | AST introspection CLI for AI agents, powered by tree-sitter | [![PyPI](https://img.shields.io/pypi/v/axm-ast)](https://pypi.org/project/axm-ast/) |
| **axm-audit** | Code auditing and quality rules for Python projects | [![PyPI](https://img.shields.io/pypi/v/axm-audit)](https://pypi.org/project/axm-audit/) |
| **axm-init** | Python project scaffolding CLI with Copier templates | [![PyPI](https://img.shields.io/pypi/v/axm-init)](https://pypi.org/project/axm-init/) |
| **axm-git** | Git workflow automation for AXM agents | [![PyPI](https://img.shields.io/pypi/v/axm-git)](https://pypi.org/project/axm-git/) |

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
    classDef ast fill:#092268,color:#ffffff,stroke:#1a3a8f
    classDef audit fill:#1a3a8f,color:#ffffff,stroke:#2a4a9f
    classDef init fill:#158DC4,color:#ffffff,stroke:#1a9dd4
    classDef git fill:#607D8B,color:#ffffff,stroke:#708D9B

    AST["axm-ast\nAST introspection"]:::ast
    AUDIT["axm-audit\nCode auditing"]:::audit --> AST
    INIT["axm-init\nScaffolding"]:::init
    GIT["axm-git\nGit automation"]:::git
```

## Development

Each package is independently versioned with prefixed tags (`ast/v*`, `audit/v*`, `init/v*`, `git/v*`).

| Command | Description |
|---|---|
| `make test-all` | Run tests for all packages |
| `make test PKG=axm-ast` | Run tests for a specific package |
| `make lint` | Ruff + mypy for all packages |
| `make check` | Full quality gate |
| `make docs` | Build documentation |

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
