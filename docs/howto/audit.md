# Run an Audit

## CLI

The fastest way to audit a project:

```bash
# Full audit
axm-audit audit .

# JSON output
axm-audit audit . --json

# Agent-optimized output (compact, actionable)
axm-audit audit . --agent

# Filter by category
axm-audit audit . --category quality

# Quick mode (lint + type only)
axm-audit audit . --quick
```

## Python API

### Full Audit

Run all checks across all categories:

```python
from pathlib import Path
from axm_audit import audit_project

result = audit_project(Path("/path/to/project"))
```

### Quick Audit

Run only linting + type checking (fastest):

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
print(json.dumps(format_json(result), indent=2))
```

### Agent Output

Optimized for AI agents — passed checks are compact strings (or dicts with actionable details like missing docstrings), failed checks include full context:

```python
from axm_audit.formatters import format_agent

data = format_agent(result)
# data["passed"]: list of strings or dicts with details
# data["failed"]: list of dicts with rule_id, message, details, fix_hint
```

### Reporters

Use the legacy reporters:

```python
from axm_audit.reporters import JsonReporter, MarkdownReporter

# JSON
print(JsonReporter().render(result))

# Markdown
print(MarkdownReporter().render(result))
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
| `audit_project(path)` | Run all checks |
| `audit_project(path, category=...)` | Filter to one category |
| `audit_project(path, quick=True)` | Lint + type only |
| `format_report(result)` | Human-readable report |
| `format_json(result)` | JSON-serializable dict |
| `format_agent(result)` | Agent-optimized output (compact passed, detailed failed) |
