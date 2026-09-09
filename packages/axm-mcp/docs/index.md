# axm-mcp

MCP transport and runtime discovery for installed AXM tools.

Start with the [Quick Start](tutorials/quickstart.md) to connect a client,
inspect the catalog and call a read-only code-analysis tool.

## What is included?

The server discovers `axm.tools` entry points from its own Python environment.
A compact facade (`axm_search`, `axm_describe`, `axm_call`,
`axm_capabilities`) keeps the direct MCP list small; the full catalog
remains reachable. Discovered tools may opt into direct exposure.

Built-ins are `verify`, `web_fetch` and `list_tools`. Their registration
does not mean their optional backends are installed. Choose the `forge`
extra for developer tools; `all` adds bibliography and tickets, but not
Scrapling. See [built-in contracts](reference/builtins.md).

## Choose a guide

| You want to… | Read |
|---|---|
| Connect for the first time | [Quick Start](tutorials/quickstart.md) |
| Add an operation | [Add a tool](howto/add-tool.md) |
| Keep one process available | [HTTP setup](howto/migration-http.md) |
| Understand quality findings | [Use verify](howto/verify.md) |
| Look up flags and paths | [CLI](reference/cli.md) / [configuration](reference/configuration.md) |
| Understand output or a missing tool | [Facade contracts](reference/facade.md) |
| Set per-session scopes | [Shared write contracts](reference/shared-contracts.md) |
| Understand implementation choices | [Architecture](explanation/architecture.md) |
| Embed or inspect the package | [Python API](reference/api/index.md) |

Stdio is the default transport. HTTP does not itself require per-session
authorization; shared policy is a separate configuration with documented
limits. Always pass explicit absolute project paths to tools on a persistent
server.
