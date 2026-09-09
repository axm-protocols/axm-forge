# Use the Verify Tool

Use `verify` to collect audit, governance and optional AST context for an
existing package. Install `axm-mcp[forge]` for all three providers, or the
individual `audit`, `init` and `ast` extras.

## Call

This is an MCP `tools/call` parameter object:

```json
{"name": "verify", "arguments": {"path": "/absolute/path/to/package"}}
```

Use a package root for package-specific results. The default is `"."`;
it refers to the server's working directory. The tool passes the path to
`audit` and `init_check` without changing their category or framework options.

## Interpret the outcome

1. Read both **audit** and **governance** sections.
2. A missing provider produces `null` in structured data and a skipped
   section in the text. This is incomplete verification, not a pass.
3. A provider failure/exception produces an `{"error": "..."}` section.
4. Inspect failed rules even if the outer tool call succeeded.
5. Treat AST context as additional impact information, not a complete
   dependency or test-coverage proof.

`VerifyTool.execute` returns `ToolResult(success=True, ...)` whenever
aggregation completes, including when sections contain findings or errors.
The tool's transport success must not be your CI quality predicate.

## Data versus text

MCP returns a compact rendered summary. The underlying Python result contains
`data={"audit": ..., "governance": ...}`. It does not add a global
`quality_ok` boolean. Provider sections retain their providers' schemas;
counts and rule sets depend on the installed versions.

When eligible audit failures contain resolvable symbols and `ast_impact`
is available, `context` may include:

| Field | Meaning |
|---|---|
| `affected_modules` | De-duplicated extracted symbol/module identifiers, despite the field name |
| `callers` | Aggregated caller dictionaries, truncated with a trailing note after the cap |
| `test_files` | De-duplicated test paths returned by AST |
| `impact_score` | Maximum ordinal label LOW, MEDIUM or HIGH |
| `symbols_analyzed` | Successful symbol analyses |

No resolvable symbols or failed AST queries means no context. Some findings
cannot be enriched.

## Operational effects

This is an orchestration convenience, not a pure in-memory check. Providers
may launch subprocesses, run tests, create reports/caches, or perform
dependency/network checks according to their own defaults. Run against a
checkout where those operations are intended. `verify` itself does not
repair findings or commit changes. For category controls or focused test
runs, discover and call the appropriate audit tool directly.
