# Use via MCP

Install `axm-audit` in the environment serving `axm-mcp`; installing it
in an unrelated target project does not add tools to an already-running
server. The server discovers `axm.tools` entry points.

## Call an audit

For a directly exposed `audit` tool, supply these arguments:

```json
{"path": "/path/to/project", "category": "lint"}
```

For a tool behind the `axm_call` façade, supply:

```json
{"name": "audit", "arguments": {"path": "/path/to/project", "category": "lint"}}
```

The façade returns rendered text. It does not expose the full structured
ToolResult payload to its caller. Direct tool registration may expose
structured content according to the MCP server's adapter. Python execution
retains `ToolResult.data` and `ToolResult.text`.

## Tests and fixes

```json
{"name": "audit_test", "arguments": {"path": "/path/to/project", "files": ["tests/unit/test_example.py"], "include_cases": true}}
```

```json
{"name": "audit_fix", "arguments": {"path": "/path/to/project", "apply": false}}
```

`audit_test` returns a pytest report; a real failed test session is a
successful measurement with `verdict=false`. `audit_fix` previews only;
its [apply behavior](../fix_pipeline.md) has additional stages and limits.

## One-shot verification

`verify` is provided by `axm-mcp`, not registered by this package.
Its argument is `path`. It combines discovered `audit` and `init_check`
results into `audit` and `governance` sections, then enriches audit failures
with AST impact context when that tool is available.

A section may be null when its tool is unavailable; this is not a passing
check. The wrapper's success is not the combined quality verdict.
It does not imply that `audit_test`, `audit_fix` or `doc_gate` ran.
Check every required section and its findings.

See [tool contracts](../reference/cli.md) for defaults and error handling.
