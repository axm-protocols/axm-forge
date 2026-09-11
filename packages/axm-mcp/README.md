<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>axm-mcp — MCP server for the axm-protocols ecosystem</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-mcp/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-mcp/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-mcp/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-mcp/"><img src="https://img.shields.io/pypi/v/axm-mcp" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://forge.axm-protocols.io/axm-mcp/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---


axm-mcp exposes installed AXM tools through MCP, with stdio or Streamable HTTP.
Its compact facade provides search, contracts and execution for the full
catalog while frequently used tools can appear directly in the client's list.

The server registers `verify`, `web_fetch` and `list_tools` itself.
Business tools are discovered from installed `axm.tools` entry points;
axm-mcp publishes no such entry point of its own.

## Features

- Discover installed `axm.tools` providers without hard-coding their catalog.
- Search tool capabilities, inspect invocation contracts and execute through
  the compact facade.
- Connect a client-managed stdio process or a persistent Streamable HTTP server.
- Inspect server health and manage its process through the `axm-mcp` CLI.

## Installation

Requires Python 3.12+ and uv. For a project-managed installation:

```bash
uv add 'axm-mcp[forge]'
```

The `forge` extra adds AST, audit, init, Git, Anvil, edit and smelt providers;
`all` additionally includes bibliography and ticketing. Neither extra includes
the optional Scrapling web backend; install the `web` extra for that backend.
The catalog depends on what is installed, not on the workspace package list.

## Quick Start

For a client-managed stdio process, use this process definition in your
client's MCP configuration. `uvx` resolves its own environment, so this route
does not require the project installation above:

```json
{
  "command": "uvx",
  "args": ["--python", "3.12", "--from", "axm-mcp[forge]", "axm-mcp"]
}
```

Client configuration wrappers differ. Save the definition and reconnect the
client; it starts the stdio process and retrieves its available MCP tools.
The base package still registers its built-ins even when their optional
providers are absent.

Call `list_tools`, then `axm_describe` for a tool's parameters and
`axm_call` to invoke it. An entry missing from MCP's direct `tools/list`
may still be in the facade. See the
[Quick Start](docs/tutorials/quickstart.md) for a complete read-only example.

## Usage

### Persistent HTTP

With the project installation above, start a persistent server:

```bash
uv run axm-mcp serve --host 127.0.0.1 --port 9427 --no-shared
uv run axm-mcp status --host 127.0.0.1 --port 9427
```

Run status in a second terminal; configure the client for Streamable HTTP at
`http://127.0.0.1:9427/mcp`. The endpoint `/health` counts directly
registered MCP tools. Pass the port explicitly: the CLI's default remains
9427 even when `AXM_MCP_PORT` is set.

Shared per-session contracts are a separate policy from HTTP transport.
They are cooperative scopes for trusted clients, not authentication.
The explicit `--shared` flag currently refuses startup; see the
[working setup and limits](docs/reference/shared-contracts.md).

## Documentation

- [Published documentation](https://forge.axm-protocols.io/axm-mcp/).

- [Quick Start](docs/tutorials/quickstart.md): connect, discover and call.
- [Add a tool](docs/howto/add-tool.md): one AXMTool and one entry point.
- [Verify a project](docs/howto/verify.md): distinguish execution success from quality results.
- [HTTP setup](docs/howto/migration-http.md): persistent process and launchd.
- [CLI](docs/reference/cli.md) and [configuration](docs/reference/configuration.md): flags, profiles and lifecycle effects.
- [Facade contracts](docs/reference/facade.md): text/data and error behavior.
- [Python API](docs/reference/api/index.md): root exports and implementation boundaries.

The README is the repository entry point; the MkDocs homepage is
[docs/index.md](docs/index.md).

## Development

This package lives in the axm-forge workspace. Build/install the checkout
before importing it: hatch-vcs generates `_version.py`. Keep documentation
validation and server tests in an isolated environment, separate from any
active MCP server.

From the workspace root, in that isolated development environment:

```bash
uv sync --all-packages --all-groups
uv run --package axm-mcp --directory packages/axm-mcp pytest
uv run --package axm-mcp --directory packages/axm-mcp --group docs mkdocs build --strict
```

The docs group supplies MkDocs and its plugins. The test command uses the
package configuration and its `tests_axm_mcp` test root.

## License

Licensed under Apache-2.0. See [LICENSE](LICENSE).
