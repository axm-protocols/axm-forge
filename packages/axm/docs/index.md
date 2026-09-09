# axm — shared SDK and command launcher

`axm` provides the shared contracts used by AXM packages and the `axm`
command that discovers their installed tools. It ships no tool of its own.
Its only runtime dependency is `cyclopts`; ecosystem packages are optional.

## Start here

- [Getting started](tutorials/getting-started.md): install a tool and inspect its CLI.
- [Write a tool](howto/write-tool.md): implement one operation for Python, CLI and MCP discovery.
- [Use a tool as a node](howto/tool-node.md): map inputs and outputs, handle failures and substitute tools.
- [CLI reference](reference/cli.md): arguments, JSON output and exit statuses.
- [SDK reference](reference/python-api.md): root imports, metadata and generated contracts.
- [Witnesses](reference/witnesses.md): validation results.
- [Architecture](explanation/architecture.md): discovery and package boundaries.

## Installation

```bash
uv add axm
uv add 'axm[init]'
uv run axm --help
uv run axm init_check --help
```

The `init` extra installs `axm-init`. Other extras are `audit`, `bib`,
and `mcp`; `all` installs these four optional packages, not the whole ecosystem.
Quote extras in shells such as zsh.

## Python entry point

```python
from axm import ToolResult

result = ToolResult(success=True, data={"count": 3}, text="3 items")
assert result.data["count"] == 3
```

The package root re-exports the shared SDK contracts. The CLI delegates domain
operations to providers; MCP transport belongs to `axm-mcp`, and DAG scheduling
belongs to `axm-dag` / `axm-loom`. See the
[architecture](explanation/architecture.md) for those boundaries.

This page is the MkDocs home page and is included in the wheel. The repository
README is a separate entry point; the complete site is built from `docs/`.
