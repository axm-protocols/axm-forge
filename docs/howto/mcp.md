# Use via MCP

`axm-init` exposes its CLI commands as MCP (Model Context Protocol) tools via `axm-mcp`. AI agents can call them directly without spawning subprocesses.

## Available Tools

| MCP Tool | Equivalent CLI | Purpose |
|---|---|---|
| `init_check` | `axm-init check` | Score a project against the AXM gold standard |
| `init_scaffold` | `axm-init scaffold` | Scaffold a new Python project |
| `init_reserve` | `axm-init reserve` | Reserve a package name on PyPI |

## Usage

!!! note "MCP dispatch"
    The examples below show the **logical API** — the parameters and return values.
    In practice, AI agents call these via MCP tool dispatch (e.g. `mcp_axm-mcp_init_check`),
    not direct Python imports.

### Check a project

```python
# Via axm-mcp
result = init_check(path="/path/to/project")
```

Returns the same structured output as `axm-init check --agent` — passed checks summarized, failed checks with full detail and fix hints.

### Scaffold a project

```python
# Via axm-mcp
result = init_scaffold(
    path="/path/to/new-project",
    name="my-project",
    org="my-org",
    author="Your Name",
    email="you@example.com",
)
```

### Reserve a package name

```python
# Via axm-mcp
result = init_reserve(name="my-package", author="Your Name", email="you@example.com")
```

## Entry Points

The tools are registered via `pyproject.toml` entry points:

```toml
[project.entry-points."axm.tools"]
init_check    = "axm_init.tools.check:InitCheckTool"
init_scaffold = "axm_init.tools.scaffold:InitScaffoldTool"
init_reserve  = "axm_init.tools.reserve:InitReserveTool"
```

`axm-mcp` discovers these automatically at startup.
