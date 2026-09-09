# Use via MCP

The same three AXMTools power the CLI and MCP. `axm-mcp` discovers their
`axm.tools` entry points in its installed environment.

| Tool | CLI | Purpose |
|---|---|---|
| `init_check` | `axm init_check` | Context- and framework-aware governance |
| `init_scaffold` | `axm init_scaffold` | Scaffolding and protocol planning/application |
| `init_reserve` | `axm init_reserve` | PyPI reservation |

## Dispatch through the facade

Tools not directly exposed by the server remain callable through
`axm_call(name=..., arguments=...)`. Client-specific MCP prefixes are not
Python function names. The following JSON objects are facade arguments.

### Check a project

```json
{"name":"init_check","arguments":{"path":"/path/to/project"}}
```

The tool's structured data follows the [check output contract](../reference/check.md).
The facade returns its text rendering.

### Scaffold a workspace

```json
{
  "name": "init_scaffold",
  "arguments": {
    "path": "/path/to/new-workspace",
    "name": "my-workspace",
    "org": "my-org",
    "author": "Your Name",
    "email": "you@example.com",
    "workspace": true
  }
}
```

For a member, use `member: "my-lib"` and the workspace path instead of
`workspace: true`. See [protocol scaffolding](scaffold-protocols.md) for
structured protocol payloads.

### Check a package name before publication

```json
{
  "name": "init_reserve",
  "arguments": {
    "name": "my-package",
    "author": "Your Name",
    "email": "you@example.com",
    "dry_run": true
  }
}
```

Set `dry_run` to false only for the actual publication. Identity and credential
rules are shared with the [CLI](../reference/reserve.md).

## Entry points

```toml
[project.entry-points."axm.tools"]
init_check    = "axm_init.tools.check:InitCheckTool"
init_scaffold = "axm_init.tools.scaffold:InitScaffoldTool"
init_reserve  = "axm_init.tools.reserve:InitReserveTool"
```
