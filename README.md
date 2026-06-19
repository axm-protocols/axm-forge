<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<h1 align="center">axm-forge</h1>
<p align="center"><strong>Developer tools for the AXM ecosystem.</strong></p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/coverage.json" alt="Coverage"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://forge.axm-protocols.io"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

## What do you need?

AXM Forge is the **developer toolchain for the AXM ecosystem** — every tool returns structured, deterministic output built for AI agents, not text to parse. Arrive with a problem, leave with the exact tool to call.

| You want to… | Use |
|---|---|
| Quality-gate a package — lint, types, complexity, security, all in one call | [`verify`](packages/axm-audit/docs/index.md) |
| Re-check one dimension (lint, types, security…) during a fix loop | [`audit`](packages/axm-audit/docs/index.md) |
| Run tests with structured pass/fail output | [`audit_test`](packages/axm-audit/docs/index.md) |
| Edit many files atomically — all of it lands or none of it does | [`batch_edit`](packages/axm-edit/docs/index.md) |
| Commit with auto-staging + conventional-commit enforcement | [`git_commit`](packages/axm-git/docs/index.md) |
| Get an overview of an unfamiliar project | [`ast_context`](packages/axm-ast/docs/index.md) |
| Find a symbol across the codebase (no grep noise) | [`ast_search`](packages/axm-ast/docs/index.md) |
| Inspect a symbol — signature, body, docstring | [`ast_inspect`](packages/axm-ast/docs/index.md) |
| Know who calls a function before you change it | [`ast_callers`](packages/axm-ast/docs/index.md) |
| Measure the blast radius of a change | [`ast_impact`](packages/axm-ast/docs/index.md) |
| Scaffold a package that passes every quality gate from day one | [`init_scaffold`](packages/axm-init/docs/index.md) |
| Find duplicate code / check a helper already exists before writing it | [`echo_code`](packages/axm-echo/docs/index.md) |

> **…and 35+ more** — CST refactoring (`ast_move`), token compaction (`smelt`), the full git workflow (`git_pr`, `git_tag`, `git_worktree`…), dead-code and flow analysis, and more. Browse them per package below or in the [docs](https://forge.axm-protocols.io).

## Packages

| Package | Description | Version | Quality |
|---|---|---|---|
| [axm](packages/axm/) | AXM CLI — thin autodiscovery wrapper for the ecosystem | [![PyPI](https://img.shields.io/pypi/v/axm)](https://pypi.org/project/axm/) | [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm/axm-audit.json)](https://forge.axm-protocols.io/audit/) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-mcp](packages/axm-mcp/) | MCP Server — runtime tool discovery and execution | [![PyPI](https://img.shields.io/pypi/v/axm-mcp)](https://pypi.org/project/axm-mcp/) | [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-mcp/axm-audit.json)](https://forge.axm-protocols.io/audit/) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-mcp/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-init](packages/axm-init/) | Python project scaffolding CLI with Copier templates | [![PyPI](https://img.shields.io/pypi/v/axm-init)](https://pypi.org/project/axm-init/) | [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-init/axm-audit.json)](https://forge.axm-protocols.io/audit/) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-init/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-audit](packages/axm-audit/) | Code auditing and quality rules for Python projects | [![PyPI](https://img.shields.io/pypi/v/axm-audit)](https://pypi.org/project/axm-audit/) | [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-audit/axm-audit.json)](https://forge.axm-protocols.io/audit/) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-audit/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-ast](packages/axm-ast/) | AST introspection CLI for AI agents, powered by tree-sitter | [![PyPI](https://img.shields.io/pypi/v/axm-ast)](https://pypi.org/project/axm-ast/) | [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ast/axm-audit.json)](https://forge.axm-protocols.io/audit/) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ast/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-git](packages/axm-git/) | Git workflow automation for AXM agents | [![PyPI](https://img.shields.io/pypi/v/axm-git)](https://pypi.org/project/axm-git/) | [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-git/axm-audit.json)](https://forge.axm-protocols.io/audit/) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-git/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-edit](packages/axm-edit/) | Atomic batch file editing for AI agents | [![PyPI](https://img.shields.io/pypi/v/axm-edit)](https://pypi.org/project/axm-edit/) | [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-edit/axm-audit.json)](https://forge.axm-protocols.io/audit/) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-edit/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-anvil](packages/axm-anvil/) | Deterministic CST-based refactoring toolkit — move, rename, split, merge symbols atomically | [![PyPI](https://img.shields.io/pypi/v/axm-anvil)](https://pypi.org/project/axm-anvil/) | [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-anvil/axm-audit.json)](https://forge.axm-protocols.io/audit/) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-anvil/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-smelt](packages/axm-smelt/) | Deterministic token compaction for LLM inputs | [![PyPI](https://img.shields.io/pypi/v/axm-smelt)](https://pypi.org/project/axm-smelt/) | [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-smelt/axm-audit.json)](https://forge.axm-protocols.io/audit/) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-smelt/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-echo](packages/axm-echo/) | Neural similarity detection — cross-package dedup and upstream-reuse retrieval | [![PyPI](https://img.shields.io/pypi/v/axm-echo)](https://pypi.org/project/axm-echo/) | [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-echo/axm-audit.json)](https://forge.axm-protocols.io/audit/) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-echo/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-ingot](packages/axm-ingot/) | Shared helper library — common code factored out and tested once, reused across packages | [![PyPI](https://img.shields.io/pypi/v/axm-ingot)](https://pypi.org/project/axm-ingot/) | [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ingot/axm-audit.json)](https://forge.axm-protocols.io/audit/) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ingot/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |

## Quick Start

### Using the tools (via MCP)

Connect the whole AXM toolchain to your MCP client (Claude Code, IDE…) in one
command — `uvx` fetches it on demand, no manual install:

```bash
claude mcp add --scope user axm-mcp -- uvx --python 3.12 --from "axm-mcp[all]@latest" axm-mcp
```

`--scope user` installs it globally (available in every session). Drop it to enable AXM per-project instead — the server then loads only in the directory where you run the command.

This exposes `verify`, `audit`, the `ast_*` family, `git_commit`, `batch_edit`,
and the rest as MCP tools. See the **[axm-mcp Quick Start](packages/axm-mcp/docs/tutorials/quickstart.md)**
for the `.mcp.json` form and the advanced persistent-HTTP setup.

Want a single tool on the CLI instead? Each package ships standalone, e.g.
`uv add axm-audit` then `axm-audit`.

### Developing the workspace

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
    classDef smelt fill:#FFA726,stroke:#FB8C00
    classDef anvil fill:#EF5350,stroke:#E53935
    classDef edit fill:#AB47BC,stroke:#8E24AA
    classDef axm fill:#66BB6A,stroke:#43A047
    classDef mcp fill:#8D6E63,stroke:#6D4C41
    classDef ingot fill:#BDBDBD,stroke:#757575
    classDef echo fill:#EC407A,stroke:#D81B60

    AXM["axm<br/>Core SDK + ToolResult"]:::axm
    INGOT["axm-ingot<br/>Shared helper library"]:::ingot
    MCP["axm-mcp<br/>MCP Server"]:::mcp --> AXM
    AST["axm-ast<br/>AST introspection"]:::ast --> AXM
    AUDIT["axm-audit<br/>Code auditing"]:::audit --> AST
    AUDIT --> ANVIL
    INIT["axm-init<br/>Scaffolding"]:::init --> AXM
    GIT["axm-git<br/>Git automation"]:::git --> AXM
    SMELT["axm-smelt<br/>Token compaction"]:::smelt --> AXM
    ANVIL["axm-anvil<br/>CST refactoring"]:::anvil --> EDIT
    EDIT["axm-edit<br/>Batch file editing"]:::edit --> AXM
    ECHO["axm-echo<br/>Neural similarity"]:::echo --> AST
    ECHO --> AXM
    AUDIT --> ECHO
    AST --> INGOT
    AUDIT --> INGOT
    INIT --> INGOT
    ANVIL --> INGOT
    ECHO --> INGOT
```

## Development

Each package is independently versioned with prefixed tags (`anvil/v*`, `ast/v*`, `audit/v*`, `echo/v*`, `edit/v*`, `init/v*`, `git/v*`, `smelt/v*`).

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
