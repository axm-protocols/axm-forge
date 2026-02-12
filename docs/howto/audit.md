# Run an Audit

## Full Audit

Run all checks across all 5 layers:

```python
from pathlib import Path
from axm_audit import audit_project

result = audit_project(Path("/path/to/project"))
```

## Quick Audit

Run only linting + type checking (fastest):

```python
result = audit_project(Path("."), quick=True)
```

## JSON Output

Use the `JsonReporter` for machine-readable output:

```python
from axm_audit.reporters import JsonReporter

reporter = JsonReporter()
print(reporter.render(result))
```

## Markdown Output

Use the `MarkdownReporter` for human-readable reports:

```python
from axm_audit.reporters import MarkdownReporter

reporter = MarkdownReporter()
print(reporter.render(result))
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
