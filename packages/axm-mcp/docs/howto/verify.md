# Use the Verify Tool

Run a one-shot quality check on any Python project.

## Basic Usage

```json
{"name": "verify", "arguments": {"path": "/path/to/project"}}
```

## What It Does

`verify` orchestrates three tools in one call:

1. **`audit`** (from `axm-audit`) — Lint, types, complexity, security, coverage, architecture
2. **`init_check`** (from `axm-init`) — 49 governance checks against AXM gold standard
3. **AST enrichment** (from `axm-ast`) — Adds caller/impact context to failures

## Output Structure

`verify` is a dual-format tool: it returns a `ToolResult` whose **`data`** is the
structured dict below (what hooks and gates read) and whose **`text`** is a
compact rendered summary (what the MCP agent sees, e.g.
`verify | audit A 97.0 (30/31) · governance A 100 (35/35)`). The `text` view is
rendered by `format_verify_text`; the `data` view is:

```json
{
  "audit": {
    "score": 93.9,
    "grade": "A",
    "passed": ["QUALITY_LINT: ok", "..."],
    "failed": [
      {
        "rule_id": "QUALITY_TYPE",
        "message": "5 errors",
        "fix_hint": "Add type hints",
        "context": {
          "affected_modules": ["foo.bar"],
          "callers": [{"symbol": "cli.main", "location": "cli.py:58"}],
          "test_files": ["tests/unit/test_foo.py"],
          "impact_score": "HIGH",
          "symbols_analyzed": 2
        }
      }
    ]
  },
  "governance": {
    "score": 90,
    "grade": "A",
    "passed": ["pyproject.exists: ok", "..."],
    "failed": []
  }
}
```

The `context` block (added by AST enrichment, `enrich_failure`) reports:

- **`impact_score`** — an **ordinal** string (`"LOW"` < `"MEDIUM"` < `"HIGH"`),
  the maximum across all analyzed symbols — **not** a numeric ratio.
- **`callers`** — a list of **dicts** (expanded from `ast_impact`'s callers), not
  bare location strings; truncated past a cap with a trailing `note` entry.
- **`test_files`** — de-duplicated test files touching the affected symbols.
- **`symbols_analyzed`** — how many symbols were successfully analyzed.

## Graceful Degradation

- If `axm-audit` is not installed → `audit` is `null`
- If `axm-init` is not installed → `governance` is `null`
- If `axm-ast` is not installed → failures have no `context` enrichment

Install more packages to get richer results.
