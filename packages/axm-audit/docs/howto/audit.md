# Run an Audit

## CLI

The fastest way to audit a project:

```bash
# Full audit
axm audit . --json-output

# Filter by category
axm audit . --json-output --category lint
```

The unified CLI auto-discovers `AuditTool` through its `axm.tools` entry point.

## Fix (test-tree reorganisation)

Apply the deterministic pyramid/file-naming fixes (RELOCATE → SPLIT →
MERGE → RENAME, then shared-helper extraction and a `ruff format`
polish). Dry-run by default; pass `--apply` to mutate the tree.

```bash
# Plan only (no mutation)
axm audit_fix .

# Mutate the tree
axm audit_fix . --apply

# Restrict to a subset of fixable rules
axm audit_fix . --apply --rules '["TEST_QUALITY_FILE_NAMING"]'
```

Only the `TEST_QUALITY_PYRAMID_LEVEL` and `TEST_QUALITY_FILE_NAMING`
findings are deterministically fixable; other rules are reported
as `unfixable` in the pipeline report. Parity of the test suite after
`--apply` is the caller's responsibility. The pipeline does not run a pytest
baseline or a test suite. Its rollback covers only `tests/`; see the
[pipeline limits](../fix_pipeline.md#convergence-and-rollback-limits).

## Python API

### Full Audit

Run all checks across all categories:

```python
from pathlib import Path
from axm_audit import audit_project

result = audit_project(Path("/path/to/project"))
```

### Quick Audit

For Python, run only linting + type checking:

```python
result = audit_project(Path("."), quick=True)
```

### Formatted Output

Use the formatters for display:

```python
from axm_audit.formatters import format_report, format_json

# Human-readable report
print(format_report(result))

# JSON-serializable dict
import json
if result.quality_score is not None:
    print(json.dumps(format_json(result), indent=2))
else:
    print("No scored measurement; inspect result.checks")
```

### Agent Output

Optimized for AI agents — passed checks are compact strings (or dicts with actionable details like missing docstrings), failed checks include full context:

```python
from axm_audit.formatters import format_agent

data = format_agent(result)
# data["passed"]: list of strings or dicts with details
# data["failed"]: list of dicts with rule_id, message, details, fix_hint
```



## Check for Failures

```python
if not result.success:
    for check in result.checks:
        if not check.passed:
            print(f"❌ {check.rule_id}: {check.message}")
            if check.fix_hint:
                print(f"   Fix: {check.fix_hint}")
```

## API Summary

| Function | Description |
|---|---|
| `audit_project(path)` | Run all checks (single-package or multi-package workspace) |
| `audit_project(path, category=...)` | Filter to one category |
| `audit_project(path, quick=True)` | Lint + type only |
| `format_report(result)` | Human-readable report |
| `format_json(result)` | JSON-serializable dict |
| `format_agent(result)` | Agent-optimized output (compact passed, detailed failed) |
| `format_agent_text(data, category=None)` | Compact text rendering of agent dict for LLM consumption |

When *path* is a multi-package workspace (`<root>/packages/<pkg>/src/`), each
package is audited independently and per-rule results are merged with a
worst-of-N policy: any failure fails the merged check, scored rules report
the minimum score across packages, and violations are prefixed with the
package name so callers can disambiguate.

### AXMTool output

Without `--json-output`, the CLI renders compact text. With that flag it
prints `ToolResult.data`; the `axm_call` MCP façade returns text only:

```bash
axm audit . --json-output
axm audit_test .
```

For Node/React/Svelte, use category selection rather than `quick=True`.
Read [framework detection](../reference/frameworks.md) and
[configuration](../reference/configuration.md) before auditing a mixed workspace.
