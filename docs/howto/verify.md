# Use the Verify Tool

Run a one-shot quality check on any Python project.

## Basic Usage

```json
{"name": "verify", "arguments": {"path": "/path/to/project"}}
```

## What It Does

`verify` orchestrates three tools in one call:

1. **`audit`** (from `axm-audit`) — Lint, types, complexity, security, coverage, architecture
2. **`init_check`** (from `axm-init`) — 39 governance checks against AXM gold standard
3. **AST enrichment** (from `axm-ast`) — Adds caller/impact context to failures

## Output Structure

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
          "callers": ["cli.py:58"],
          "impact_score": 0.7
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

## Graceful Degradation

- If `axm-audit` is not installed → `audit` is `null`
- If `axm-init` is not installed → `governance` is `null`
- If `axm-ast` is not installed → failures have no `context` enrichment

Install more packages to get richer results.
