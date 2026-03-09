<div class="hero" markdown>

<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-init/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<h1 align="center">axm-forge</h1>
<p align="center"><strong>Developer tools for the AXM ecosystem — AST introspection, code auditing, project scaffolding, and git automation.</strong></p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/license-Apache%202.0-green" alt="License">
</p>

</div>

---

## Workspace Packages

| Package | Description | Version |
|---|---|---|
| **[axm-ast](ast/)** | AST introspection CLI for AI agents, powered by tree-sitter | [![PyPI](https://img.shields.io/pypi/v/axm-ast)](https://pypi.org/project/axm-ast/) |
| **[axm-audit](audit/)** | Code auditing and quality rules for Python projects | [![PyPI](https://img.shields.io/pypi/v/axm-audit)](https://pypi.org/project/axm-audit/) |
| **[axm-init](init/)** | Python project scaffolding CLI with Copier templates | [![PyPI](https://img.shields.io/pypi/v/axm-init)](https://pypi.org/project/axm-init/) |
| **[axm-git](git/)** | Git workflow automation for AXM agents | [![PyPI](https://img.shields.io/pypi/v/axm-git)](https://pypi.org/project/axm-git/) |

## Quick Start

```bash
# Install the workspace
uv sync --all-groups

# Run all tests
make test-all

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

    AST["axm-ast<br/><i>AST introspection</i>"]:::ast
    AUDIT["axm-audit<br/><i>Code auditing</i>"]:::audit --> AST
    INIT["axm-init<br/><i>Scaffolding</i>"]:::init
    GIT["axm-git<br/><i>Git automation</i>"]:::git
```

## Learn More

- **New here?** Start with a package's Getting Started tutorial
- **Building tools?** See the How-To Guides in each package
- **Understanding the design?** Read the Architecture explanations
