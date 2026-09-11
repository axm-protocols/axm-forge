<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>AXM — Shared SDK and unified command launcher</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm/"><img src="https://img.shields.io/pypi/v/axm" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://forge.axm-protocols.io/axm/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

AXM provides the shared Python contracts for AXM tools and the `axm` command
launcher. Install provider packages to add commands; the SDK itself does not
ship domain tools or run an MCP server.

## Features

- **Shared SDK** — `AXMTool`, `ToolResult`, discovery metadata,
  witness contracts, and the `tool_node` adapter.
- **Lazy CLI discovery** — list installed entry points without importing every
  provider; load the requested command when dispatched.
- **One tool declaration** — `axm.tools` connects a provider to the generic CLI,
  MCP discovery and tool-node resolution.
- **Small runtime** — only Cyclopts is required; ecosystem providers are optional.

## Installation

Requires Python 3.12 or newer. In a Python project managed by uv:

```bash
uv add axm                  # SDK and launcher; no domain tools
uv add 'axm[init]'           # scaffolding and project checks
uv add 'axm[audit]'          # code quality
uv add 'axm[bib]'            # bibliography provider
uv add 'axm[mcp]'            # MCP server package
uv add 'axm[all]'            # the four optional providers above
```

With an activated virtual environment, `pip install 'axm[init]'` is an
alternative. Quote extras in shells such as zsh. `all` does not install every
package in the AXM ecosystem.

## Quick Start

After `uv add axm`, create a structured result without installing a provider:

```bash
uv run python - <<'PY'
from axm import ToolResult

result = ToolResult(success=True, data={"count": 3}, text="3 items")
print(result.text)
print(result.data["count"])
PY
```

This prints `3 items` followed by `3`. Tools return the same contract to expose
structured data alongside readable output.

## Usage

### Unified CLI

With the `init` extra installed, run from the project environment:

```bash
uv run axm --help
uv run axm --version
uv run axm init_check --help
uv run axm init_check --path . --json-output
```

The catalog depends on installed providers. Use a command's help for its
actual options. Generated commands normally print `ToolResult.text` or fall
back to data; the shared `--json-output` emits the data mapping. Failures remain
nonzero. A provider with its own `json_output` parameter owns that flag's
behavior. See the [CLI reference](docs/reference/cli.md).

### Shared Python contracts

```python
from axm import AXMTool, ToolResult, tool_node

result = ToolResult(success=True, data={"count": 3}, text="3 items")
assert result.data["count"] == 3
```

The root also exports `ToolMetadata`, `tool_metadata`, `ToolNodeError`,
`WitnessRule`, `WitnessResult`,
`ValidationFeedback` and `__version__`. See the
[SDK reference](docs/reference/python-api.md) and
[witnesses](docs/reference/witnesses.md) for their contracts.

### How It Works

A provider registers an implementation in its `pyproject.toml`:

```toml
[project.entry-points."axm.tools"]
demo_count = "demo_tools.count:CountTool"
```

This is an illustrative provider, implemented in the
[write-a-tool guide](docs/howto/write-tool.md). The CLI derives arguments from
its `execute` signature. Only `axm.tools` extends the unified launcher.

## Documentation

- [Getting started](docs/tutorials/getting-started.md)
- [Write a tool](docs/howto/write-tool.md)
- [Compose a tool node](docs/howto/tool-node.md)
- [Architecture](docs/explanation/architecture.md)
- [Published documentation](https://forge.axm-protocols.io/axm/)

The MkDocs home page is [docs/index.md](docs/index.md); it is separate from this
README. The package has a standalone MkDocs configuration and also participates
in the workspace site.

## Development

This package belongs to the **axm-forge** workspace.

```bash
git clone https://github.com/axm-protocols/axm-forge.git
cd axm-forge
uv sync --all-packages --all-groups
uv run --package axm --directory packages/axm pytest
```

From `packages/axm`, build the package documentation with
`mkdocs build --strict` in an environment containing the package's docs
dependencies.

### Package Structure

```text
src/axm/
  __init__.py          # root SDK exports and version
  cli.py               # command discovery and rendering
  tools/base.py        # tool protocol, result and metadata
  tools/node.py        # tool-node adapter and scoped substitutes
  tools/write_scope.py # internal write-scope decisions
  witnesses.py         # validation contracts
tests_axm/             # package tests
docs/                  # tutorials, guides, reference and explanations
```

## License

Licensed under Apache-2.0. See [LICENSE](LICENSE).
