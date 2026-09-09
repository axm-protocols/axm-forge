# Getting Started

Start with the [Quick Start](quickstart.md): select a tool set, connect over
stdio, inspect the catalog and call a read-only tool against a local package.
That tutorial is the canonical first-run walkthrough.

## Choose your next path

| Your goal | Guide |
|---|---|
| Connect an MCP client for the first time | [Quick Start](quickstart.md) |
| Keep a server running between client sessions | [HTTP setup](../howto/migration-http.md) |
| Expose an existing Python operation | [Add a tool](../howto/add-tool.md) |
| Understand a project's quality findings | [Verify](../howto/verify.md) |
| Diagnose a missing tool or unexpected output | [Facade reference](../reference/facade.md) |

The server package supplies the transport and discovery. Installed optional
packages determine the business tools available. Start with stdio unless you
need a persistent process and can manage its configuration and lifetime.
