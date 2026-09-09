# Python API

The package root exports **`main` and `__version__`** through
`axm_mcp.__all__`. This is a server package; use MCP to call its built-ins.

## Version

```python
from axm_mcp import __version__

assert isinstance(__version__, str)
```

The version comes from hatch-vcs-generated `_version.py`. A raw source
checkout needs a package build/install before importing the root;
the generated file is not a manually maintained source file.

## CLI entry point

::: axm_mcp.main

`main()` invokes the lifecycle command parser using process arguments. It
may start a long-lived server or perform service-management actions; it is
not a request/response API to invoke a tool.

## Implementation seams

The following are useful when embedding/testing this implementation, but are
**not exported at the package root**. Their signatures and lifecycles should
be reviewed against the installed version before integration.

| Import | Contract / caution |
|---|---|
| `axm_mcp.discovery.discover_tools` | Instantiate installed entry points; loading can execute plugin initialization |
| `axm_mcp.facade.ToolCatalog` | Index a supplied entry map; `call` returns text synchronously, `acall` uses the async wrapper |
| `axm_mcp.mcp_app.build_http_app` | Build the registered MCPServer ASGI application; importing the module already discovers tools |
| `axm_mcp.server.serve` | Run HTTP; unlike CLI, a missing port can use the environment |
| `axm_mcp.verify.verify_project` | Aggregate using a supplied provider mapping; no global pass boolean |
| `axm_mcp.web_fetch.fetch_page` | Async optional-backend fetch; result is a dictionary |
| `axm_mcp.session_contracts.SessionContractRegistry` | In-memory bind/resolve/release/explicit purge; expiry is not automatic |
| `axm_mcp.settings.NonProductionPortError` | Missing explicit environment port in non-production descriptor resolution |
| `axm_mcp.server.SharedModeNotArmedError` | Lower-level shared serving requested without a resolver |
| `axm_mcp.session_contracts.UnboundSessionError` | Missing session identity or contract |
| `axm_mcp.session_contracts.WriteContractHeaderError` | Invalid strict contract-header payload |
| `axm_mcp.facade.catalog.UnknownToolError` | A requested name is not in the supplied catalog |

The lifecycle and HTTP middleware require their own setup; importing
`build_http_app` is not equivalent to executing the CLI's shared startup.
Prefer the supported [CLI](../cli.md) for launching the server.
