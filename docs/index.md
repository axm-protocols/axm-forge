<div class="hero" markdown>

<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<h1 align="center">axm-forge</h1>
<p align="center"><strong>Developer tools for the AXM ecosystem — AST introspection, code auditing, project scaffolding, and git automation.</strong></p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/coverage.json" alt="Coverage"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/license-Apache%202.0-green" alt="License">
</p>

</div>

---

## Philosophy

AXM Forge provides the **developer toolchain** for the AXM ecosystem. Every tool returns structured, deterministic results — designed for AI agents that need precise answers, not text to parse.

<div class="grid cards" markdown>

-   :material-cube-outline:{ .lg .middle } **Automated Scaffolding**

    ---

    Generate projects, workspaces, and workspace members that pass all 39 governance checks from day one. Copier templates encode AXM conventions so every new package starts production-ready.

-   :material-shield-check:{ .lg .middle } **Codified Quality Gates**

    ---

    40+ rules covering lint, types, coverage, complexity, security, and project governance — all in a single `verify()` call. Scores and grades make quality measurable and comparable.

-   :material-file-tree:{ .lg .middle } **AST-Powered Introspection**

    ---

    Tree-sitter based analysis that understands Python at the structural level. Find callers, measure blast radius, and trace import graphs — all without grep noise. Every query returns precise, semantic results.

-   :material-source-branch:{ .lg .middle } **Git Workflow Automation**

    ---

    Structured commits with auto-staging, commit-hook retry, and conventional commit enforcement. Semver tagging and push — all through agent-friendly MCP tools.

-   :material-file-replace-outline:{ .lg .middle } **Atomic Batch Editing**

    ---

    Replace, create, and delete across dozens of files in a single transactional call. No partial writes, no half-applied refactors — it all lands or none of it does.

-   :material-hammer-wrench:{ .lg .middle } **CST-Based Refactoring**

    ---

    Move, rename, split, and merge symbols across a codebase without breaking a single import. Concrete syntax trees keep every reference in sync.

-   :material-arrow-collapse-vertical:{ .lg .middle } **Token Compaction**

    ---

    Deterministic strategies to shrink LLM inputs — whitespace collapse, null stripping, table compaction, deduplication — with presets from safe to aggressive. Fit more context, spend fewer tokens.

</div>

## Workspace Packages

| Package | Description | Version | Quality |
|---|---|---|---|
| **[axm](axm/index.md)** | AXM CLI — thin autodiscovery wrapper for the ecosystem | [![PyPI](https://img.shields.io/pypi/v/axm)](https://pypi.org/project/axm/) | [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| **[axm-mcp](mcp/index.md)** | MCP Server — runtime tool discovery and execution | [![PyPI](https://img.shields.io/pypi/v/axm-mcp)](https://pypi.org/project/axm-mcp/) | [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-mcp/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-mcp/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| **[axm-init](init/index.md)** | Python project scaffolding CLI with Copier templates | [![PyPI](https://img.shields.io/pypi/v/axm-init)](https://pypi.org/project/axm-init/) | [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-init/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-init/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| **[axm-audit](audit/index.md)** | Code auditing and quality rules for Python projects | [![PyPI](https://img.shields.io/pypi/v/axm-audit)](https://pypi.org/project/axm-audit/) | [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-audit/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-audit/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| **[axm-ast](ast/index.md)** | AST introspection CLI for AI agents, powered by tree-sitter | [![PyPI](https://img.shields.io/pypi/v/axm-ast)](https://pypi.org/project/axm-ast/) | [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ast/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ast/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| **[axm-git](git/index.md)** | Git workflow automation for AXM agents | [![PyPI](https://img.shields.io/pypi/v/axm-git)](https://pypi.org/project/axm-git/) | [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-git/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-git/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| **[axm-edit](edit/index.md)** | Atomic batch file editing for AI agents | [![PyPI](https://img.shields.io/pypi/v/axm-edit)](https://pypi.org/project/axm-edit/) | [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-edit/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-edit/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| **[axm-anvil](anvil/index.md)** | Deterministic CST-based refactoring toolkit — move, rename, split, merge symbols atomically | [![PyPI](https://img.shields.io/pypi/v/axm-anvil)](https://pypi.org/project/axm-anvil/) | [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-anvil/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-anvil/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| **[axm-smelt](smelt/index.md)** | Deterministic token compaction for LLM inputs | [![PyPI](https://img.shields.io/pypi/v/axm-smelt)](https://pypi.org/project/axm-smelt/) | [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-smelt/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-smelt/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| **[axm-ingot](ingot/index.md)** | Shared helper library — common code factored out and tested once, reused across packages | [![PyPI](https://img.shields.io/pypi/v/axm-ingot)](https://pypi.org/project/axm-ingot/) | [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ingot/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ingot/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |

## Quick Start

### Using the tools (via MCP)

Connect the whole AXM toolchain to your MCP client (Claude Code, IDE…) in one
command — `uvx` fetches it on demand, no manual install:

```bash
claude mcp add --scope user axm-mcp -- uvx --python 3.12 --from "axm-mcp[all]@latest" axm-mcp
```

This exposes `verify`, `audit`, the `ast_*` family, `git_commit`, `batch_edit`,
and the rest as MCP tools. See the **[axm-mcp Quick Start](mcp/tutorials/quickstart.md)**
for the `.mcp.json` form and the advanced persistent-HTTP setup.

### Developing the workspace

```bash
# Install the workspace
uv sync --all-groups

# Run all tests
make test-all

# Lint + type check
make lint

# Full AXM quality gate (pre-push)
make quality
```

## Architecture

```mermaid
%%{ init: { "flowchart": { "defaultRenderer": "elk" } } }%%
graph TD
    classDef ast fill:#5C6BC0,stroke:#3949AB,color:#fff
    classDef audit fill:#42A5F5,stroke:#1E88E5,color:#fff
    classDef init fill:#26C6DA,stroke:#00ACC1,color:#fff
    classDef git fill:#78909C,stroke:#546E7A,color:#fff
    classDef smelt fill:#FFA726,stroke:#FB8C00,color:#fff
    classDef anvil fill:#EF5350,stroke:#E53935,color:#fff
    classDef edit fill:#AB47BC,stroke:#8E24AA,color:#fff
    classDef axm fill:#66BB6A,stroke:#43A047,color:#fff
    classDef mcp fill:#8D6E63,stroke:#6D4C41,color:#fff
    classDef ingot fill:#BDBDBD,stroke:#757575,color:#000

    subgraph tools [Tools]
        direction TB

        AUDIT["axm-audit<br/>Code auditing"]:::audit
        ANVIL["axm-anvil<br/>CST refactoring"]:::anvil

        subgraph botrow [ ]
            direction LR
            AST["axm-ast<br/>AST introspection"]:::ast
            EDIT["axm-edit<br/>Batch file editing"]:::edit
            INIT["axm-init<br/>Scaffolding"]:::init
            GIT["axm-git<br/>Git automation"]:::git
            SMELT["axm-smelt<br/>Token compaction"]:::smelt
        end

        AUDIT --> AST
        AUDIT --> ANVIL
        ANVIL --> EDIT
    end

    subgraph foundations [Foundations]
        direction TB
        subgraph baserow [ ]
            direction LR
            MCP["axm-mcp<br/>MCP Server"]:::mcp
            AXM["axm<br/>Core SDK + ToolResult"]:::axm
            INGOT["axm-ingot<br/>Shared helper library"]:::ingot
        end
    end

    %% the whole tool layer builds on the shared foundations
    %% (target a node inside baserow so ELK fills + aligns that row)
    tools --> AXM

    %% hide the inner row containers (keep only Tools / Foundations frames)
    style botrow fill:none,stroke:none
    style baserow fill:none,stroke:none
```

## Learn More

- **New here?** Start with the [axm-ast Quick Start](ast/tutorials/quickstart.md) tutorial
- **Auditing code?** See the [axm-audit Getting Started](audit/tutorials/getting-started.md)
- **Scaffolding projects?** Read the [axm-init docs](init/index.md)
- **Git automation?** Check [axm-git](git/index.md)
- **Token compaction?** See [axm-smelt](smelt/index.md)
- **Factoring shared helpers?** See [axm-ingot](ingot/index.md)
