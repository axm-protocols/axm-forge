# CLI and tools

The package registers four `axm.tools` entry points. There is no
`axm-audit` executable. The installed generic `axm` CLI derives its
parameters from each tool's `execute()` signature.

## Common CLI behavior

`PATH` defaults to `.` and can be positional or supplied with `--path`.
By default, output is compact text. `--json-output` prints the tool's
`data` payload as JSON, not the enclosing ToolResult and not
`format_json(AuditResult)`.

List-valued CLI arguments are JSON arrays encoded as one shell argument:

```bash
axm audit . --category lint --json-output
axm audit_test . --files '["tests/unit/test_example.py"]' --include-cases --json-output
axm audit_fix . --rules '["TEST_QUALITY_FILE_NAMING"]'
axm doc_gate . --timeout 120 --json-output
```

`axm <tool> --help` reports the installed signature. All four commands
support `--json-output`. MCP uses native lists and booleans, not their
shell-quoted JSON representation.

## Audit

| Argument | Default | Contract |
|---|---|---|
| `path` | `"."` | Existing project directory |
| `category` | `None` | One category, or all when omitted |

[Categories](../howto/categories.md) are validated by the auditor. Invalid
categories and non-directory paths are tool errors. Framework detection
is automatic; `quick` and `framework` belong to the Python API only.

`data` contains `score`, `grade`, `passed` and `failed`.
The first two may be null. Failed entries can contain both `text` and
`details`, plus `metadata` and `fix_hint` when present.
Lists inside individual rule details may be bounded summaries.

`ToolResult.success=True` means the audit completed, even with failed
checks. Consequently exit status alone is not a quality gate.
Require an empty `failed` list and whatever scored coverage your policy needs.
The tool also attempts best-effort quality/code metric snapshots.

## Structured tests

| Argument | Default | Contract |
|---|---|---|
| `path` | `"."` | pytest project root |
| `files` | `None` | Explicit test paths; disables the runner's coverage collection |
| `markers` | `None` | pytest marker filters |
| `stop_on_first` | `True` | CLI: `--no-stop-on-first` runs past the first failure |
| `include_cases` | `False` | Add per-item node ID, outcome and detail |
| `mode` | `"failures"` | `"cases"` also enables per-item evidence; other values do not select a distinct report format |

The payload includes counts, duration, coverage, failures,
`pytest_return_code`, `collected`, `target_statuses`, `timed_out`,
`verdict` and `non_test_cause`. `cases` is omitted unless requested.

A genuine pytest session with failing tests can return tool success and exit
zero: inspect `verdict`. Zero collected tests, invalid/unvalidated targets,
collection or usage errors, timeouts and non-test causes are tool failures.
The runner uses a 900-second subprocess timeout. With case evidence requested,
a timeout is returned as an error rather than a partial report.

## Fix

| Argument | Default | Contract |
|---|---|---|
| `path` | `"."` | Python project directory |
| `apply` | `False` | Preview, or mutate with `--apply` |
| `rules` | `None` | Rule IDs selecting pipeline stages |

The report contains `ops`, `applied`, `warnings`, `unfixable`,
`iterations` and operation counts. A dry-run is one planning pass, not
an exhaustive simulation of apply. Read the [pipeline reference](../fix_pipeline.md)
for supported stages, test-directory assumptions and rollback limits.

## Documentation gate

| Argument | Default | Contract |
|---|---|---|
| `path` | `"."` | Directory containing `mkdocs.yml` |
| `timeout` | `120` | MkDocs subprocess timeout in seconds |

Runs `mkdocs build --strict` into a temporary site directory using
`mkdocs` from PATH. The temporary site is removed afterwards.
The successful payload has `findings` and `count`. A failed build with
recognized findings can still return tool success: require `count == 0`.
Missing MkDocs, timeout, or an unclassified build failure returns tool error.
It does not independently crawl all generated HTML or external URLs.

## Errors and transport

The generic CLI exits nonzero for `ToolResult.success=False`.
Tool errors can print an error on stderr and an empty JSON data object;
do not ignore exit status before parsing JSON.

Direct Python tool execution returns `ToolResult`. MCP registration may
shape it further; the `axm_call` façade returns rendered text only.
See [MCP usage](../howto/mcp.md) and the [Python API](python-api.md).
