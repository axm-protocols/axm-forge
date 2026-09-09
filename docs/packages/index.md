# Packages

Choose a package by responsibility. All 14 members share this repository and
uv lockfile, but each has its own version, tests and documentation.

| Package | Responsibility | Quality |
|---|---|---|
| [axm](../axm/index.md) | Core SDK (AXMTool, ToolResult, tool_node) and generic CLI [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-mcp](../axm-mcp/index.md) | MCP server, tool catalog, facade and transports [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-mcp/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-mcp/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-ast](../ast/index.md) | Read-only structural analysis with tree-sitter [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ast/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ast/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-anvil](../anvil/index.md) | Python symbol move, rename and extraction [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-anvil/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-anvil/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-edit](../edit/index.md) | Batch edits, checkpoints and filesystem tools [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-edit/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-edit/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-audit](../audit/index.md) | Quality rules, test execution and test refactoring [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-audit/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-audit/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-init](../init/index.md) | Scaffolding and project governance checks [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-init/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-init/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-git](../axm-git/index.md) | Git commits, branches, worktrees and release operations [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-git/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-git/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-echo](../axm-echo/index.md) | Code similarity and reuse-candidate retrieval [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-echo/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-echo/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-smelt](../smelt/index.md) | Text compaction and token measurement [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-smelt/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-smelt/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-ingot](../ingot/index.md) | Dependency-free shared Python helpers [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ingot/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ingot/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-config](../axm-config/index.md) | Non-sensitive configuration and runtime paths [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-config/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-config/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-vault](../axm-vault/index.md) | Credential catalog and secret resolution [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-vault/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-vault/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-doctor](../axm-doctor/index.md) | Environment/bootstrap and authentication diagnostics [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-doctor/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-doctor/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |

## Choose an interface

- **Python:** install the package whose public API you need. Start at its
  reference; internal modules are not automatically a stable contract.
- **CLI:** installed `axm.tools` providers are discovered by the `axm`
  executable. Some packages also have dedicated commands; consult their
  CLI reference rather than deriving a command from the package name.
- **MCP:** run [axm-mcp](../axm-mcp/index.md) in the same environment as the
  providers. The facade catalog can contain more tools than the direct
  MCP tool list.
- **DAG:** [tool_node](../axm/index.md) adapts registered tools. The DAG
  runtime and graph-authoring packages are outside Forge.

`axm-ingot` is a library with no tool entry points.
`axm` provides the SDK and CLI; `axm-mcp` provides the server and its
meta-tools rather than an `axm.tools` provider.

## Architecture

Start with the [workspace boundaries](../explanation/architecture.md).
For JS/TS projects, use the [Node/Svelte support overview](../node-svelte/index.md);
Python runtime requirements and target-language support are separate concerns.
