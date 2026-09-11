<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<h1 align="center">axm-forge</h1>
<p align="center"><strong>Developer tools and the SDK that connects them.</strong></p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-audit.json" alt="axm-audit"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/coverage.json" alt="Coverage"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://forge.axm-protocols.io"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

AXM Forge is a uv workspace of independently versioned Python packages for
code analysis, quality checks, editing, scaffolding and Git operations.
Use the tools through an MCP client or the generic `axm` CLI; use the
libraries directly when integrating them into Python applications.

## What do you need?

| You want to… | Start here |
|---|---|
| Understand a project or find a symbol | [axm-ast](packages/axm-ast/docs/index.md): `ast_context`, `ast_search`, `ast_inspect` |
| Audit a package or run its tests | [axm-audit](packages/axm-audit/docs/index.md): `audit`, `audit_test` |
| Combine audit and governance checks over MCP | [axm-mcp](packages/axm-mcp/docs/howto/verify.md): `verify` |
| Validate and apply a batch of edits | [axm-edit](packages/axm-edit/docs/index.md): `batch_edit_check`, `batch_edit` |
| Move, rename or extract Python symbols | [axm-anvil](packages/axm-anvil/docs/index.md): `anvil_move`, `anvil_rename`, `anvil_extract` |
| Scaffold a project and check its conventions | [axm-init](packages/axm-init/docs/index.md): `init_scaffold`, `init_check` |
| Review repository state and commit changes | [axm-git](packages/axm-git/docs/index.md): `git_preflight`, `git_commit` |
| Find duplicate code or possible reuse | [axm-echo](packages/axm-echo/docs/index.md): `echo_code`, `echo_check` |
| Reduce text size or count tokens | [axm-smelt](packages/axm-smelt/docs/index.md): `smelt`, `smelt_count` |

Check each tool's result and documented limits. A successful invocation does
not necessarily mean a passing audit or test suite. Batch editing uses validation
and rollback, but does not provide a filesystem-wide transaction. Similarity
scores identify candidates for review, not proof of equivalent behavior.

## Packages

The workspace root is development infrastructure; install the packages you need.

| Package | Role | Release | Quality |
|---|---|---|---|
| [axm](packages/axm/) | Core SDK (AXMTool, ToolResult, tool_node) and generic CLI | [![PyPI](https://img.shields.io/pypi/v/axm)](https://pypi.org/project/axm/) [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-mcp](packages/axm-mcp/) | MCP server, tool catalog, facade and transports | [![PyPI](https://img.shields.io/pypi/v/axm-mcp)](https://pypi.org/project/axm-mcp/) [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-mcp/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-mcp/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-ast](packages/axm-ast/) | Read-only structural analysis with tree-sitter | [![PyPI](https://img.shields.io/pypi/v/axm-ast)](https://pypi.org/project/axm-ast/) [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ast/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ast/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-anvil](packages/axm-anvil/) | Python symbol move, rename and extraction | [![PyPI](https://img.shields.io/pypi/v/axm-anvil)](https://pypi.org/project/axm-anvil/) [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-anvil/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-anvil/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-edit](packages/axm-edit/) | Batch edits, checkpoints and filesystem tools | [![PyPI](https://img.shields.io/pypi/v/axm-edit)](https://pypi.org/project/axm-edit/) [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-edit/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-edit/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-audit](packages/axm-audit/) | Quality rules, test execution and test refactoring | [![PyPI](https://img.shields.io/pypi/v/axm-audit)](https://pypi.org/project/axm-audit/) [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-audit/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-audit/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-init](packages/axm-init/) | Scaffolding and project governance checks | [![PyPI](https://img.shields.io/pypi/v/axm-init)](https://pypi.org/project/axm-init/) [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-init/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-init/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-git](packages/axm-git/) | Git commits, branches, worktrees and release operations | [![PyPI](https://img.shields.io/pypi/v/axm-git)](https://pypi.org/project/axm-git/) [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-git/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-git/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-echo](packages/axm-echo/) | Code similarity and reuse-candidate retrieval | [![PyPI](https://img.shields.io/pypi/v/axm-echo)](https://pypi.org/project/axm-echo/) [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-echo/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-echo/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-smelt](packages/axm-smelt/) | Text compaction and token measurement | [![PyPI](https://img.shields.io/pypi/v/axm-smelt)](https://pypi.org/project/axm-smelt/) [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-smelt/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-smelt/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-ingot](packages/axm-ingot/) | Dependency-free shared Python helpers | [![PyPI](https://img.shields.io/pypi/v/axm-ingot)](https://pypi.org/project/axm-ingot/) [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ingot/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-ingot/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-config](packages/axm-config/) | Non-sensitive configuration and runtime paths | [![PyPI](https://img.shields.io/pypi/v/axm-config)](https://pypi.org/project/axm-config/) [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-config/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-config/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-vault](packages/axm-vault/) | Credential catalog and secret resolution | [![PyPI](https://img.shields.io/pypi/v/axm-vault)](https://pypi.org/project/axm-vault/) [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-vault/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-vault/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |
| [axm-doctor](packages/axm-doctor/) | Environment/bootstrap and authentication diagnostics | [![PyPI](https://img.shields.io/pypi/v/axm-doctor)](https://pypi.org/project/axm-doctor/) [![audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-doctor/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) [![cov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-doctor/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml) |

## Quick Start

### Using the tools via MCP

Both transports are supported:

- **stdio** is the simplest first installation: the client starts and stops
  its own server process. The configuration below uses this mode.
- **Streamable HTTP** suits a persistent server used by several clients.
  Start it with `axm-mcp serve` and connect clients to `/mcp`; follow the
  [HTTP setup guide](packages/axm-mcp/docs/howto/migration-http.md).

Running `axm-mcp` without a subcommand still selects stdio.

With Python 3.12+ and uv installed, configure your MCP client to start this
stdio server process:

```json
{
  "command": "uvx",
  "args": ["--python", "3.12", "--from", "axm-mcp[forge]", "axm-mcp"]
}
```

The enclosing configuration and its scope depend on your client.
The `forge` extra installs the main developer-tool packages; it is not a
promise to install every package in this repository. `all` additionally
includes bibliography and ticket packages from other workspaces. Pin versions
for reproducible environments.

The default facade exposes discovery and dispatch tools alongside selected
direct tools. Use `axm_search`, `axm_describe` and `axm_call` to reach
the installed catalog. The server and tool providers must share one Python
environment. Follow the [MCP quick start](packages/axm-mcp/docs/tutorials/quickstart.md)
for a verified discovery/call sequence and HTTP setup.

### Using one tool from a terminal

This example installs axm and the AST provider into a temporary uv tool
environment, then prints help without analysing a project:

```bash
uvx --with axm-ast --from axm axm ast_context --help
```

Package names and executable names are not interchangeable:
`axm-audit`, `axm-edit` and `axm-init` expose tools through `axm`,
not standalone executables of those names.

### Developing the workspace

```bash
git clone https://github.com/axm-protocols/axm-forge.git
cd axm-forge
uv sync --all-packages --all-groups
uv run --package axm-edit --directory packages/axm-edit pytest --cov
uv run mkdocs build --strict
```

[Contributing](CONTRIBUTING.md) covers package-specific checks, the current
Makefile limitations, hooks and documentation previews.

## Architecture

`axm` supplies the shared tool contract and CLI discovery.
`axm-mcp` exposes installed providers through MCP. Tool packages implement
operations; libraries such as `axm-ingot` can also be used without a server.
`tool_node` adapts a registered tool for a DAG, whose runtime lives outside
this workspace.

See the [workspace architecture](https://forge.axm-protocols.io/explanation/architecture/)
for package boundaries and the [package catalog](https://forge.axm-protocols.io/packages/)
for individual tutorials and API references.

## Development

Packages use their full name as a Git tag prefix, for example
`axm-ast/v0.5.2` or `axm/v0.8.0`. The publish workflow derives
`packages/<name>` from that prefix. Tagging is a release operation;
pushing documentation to main does not publish a package version.

The build and upload jobs have separate conditions. Consult the
[publish workflow](.github/workflows/publish.yml) before a release.

A package declares once, through the `Private :: Do Not Upload`
classifier, that it must never leave the monorepo. Both release
workflows read that marker from the shared
[detect-package action](.github/actions/detect-package/action.yml):
the PyPI upload is withheld, and so is the GitHub Release, whose
generated notes would otherwise publish the changelog the package is
meant to keep in-house. Tagging, versioning and tests still run — only
the publication stops. PyPI independently rejects the `Private ::`
prefix on upload, so the classifier is a double safety net.

## License

Apache 2.0 — see [LICENSE](LICENSE).
