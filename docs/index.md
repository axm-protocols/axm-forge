# axm-forge

**Developer tools and the SDK that connects them.**

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-audit.json" alt="axm-audit"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/coverage.json" alt="Coverage"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://forge.axm-protocols.io"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

Analyse code, check quality, edit files and automate Git workflows through
Python libraries, a CLI or MCP. Forge is a workspace of independent packages:
choose the capability you need and install its provider alongside your client
interface.

## Start with your task

<div class="grid cards" markdown>

-   :material-file-tree:{ .lg .middle } **Understand code**

    Find symbols, inspect signatures and trace callers with
    [axm-ast](ast/index.md).

-   :material-shield-check:{ .lg .middle } **Check a project**

    Run [quality rules and tests](audit/index.md), check
    [project conventions](init/index.md), or combine them through
    [MCP verify](axm-mcp/howto/verify.md).

-   :material-file-replace-outline:{ .lg .middle } **Make a change**

    Use [axm-edit](edit/index.md) for batches of file edits and
    [axm-anvil](anvil/index.md) for Python symbol refactoring.
    Review validation, rollback and post-processing limits before applying changes.

-   :material-source-branch:{ .lg .middle } **Manage the workflow**

    Inspect and commit with [axm-git](axm-git/index.md), find reuse candidates
    with [axm-echo](axm-echo/index.md), or compact context with
    [axm-smelt](smelt/index.md).

</div>

## Quick Start

- **MCP client:** use the [stdio quick start](axm-mcp/tutorials/quickstart.md)
  for a client-managed process, or the [HTTP setup](axm-mcp/howto/migration-http.md)
  for a persistent server shared by several clients. Both transports are supported.
- **Local checkout:** follow [your first workspace query](tutorials/getting-started.md).
- **Choose a package:** browse the [complete catalog](packages/index.md),
  including configuration, secrets and environment diagnostics.
- **Contribute:** use the [development guide](contributing.md).

## Philosophy

Tools return a shared result envelope, but each operation has its own data,
failure conditions and effects. Read the returned quality verdicts and errors;
successful dispatch alone does not prove a project is healthy.

Code analysis and similarity results have limits. Editing tools validate
requests and attempt recovery; they cannot guarantee an all-or-nothing
transaction across every file and post-processing step. Package references
describe those contracts.

## Architecture

The [architecture guide](explanation/architecture.md) explains SDK, transport,
analysis, mutation and runtime-configuration boundaries.
The [Node/Svelte overview](node-svelte/index.md) describes current support and links to package contracts.

## Workspace Packages

The [package catalog](packages/index.md) lists all 14 members and their entry
points. Each package owns its tutorials, guides and API reference; this
workspace documentation covers installation, composition and contribution.

## Learn More

- [Build and preview the documentation](howto/documentation.md).
- [Create a tool provider](axm-mcp/howto/add-tool.md).
- [Use a tool in a DAG](axm/howto/tool-node.md).
