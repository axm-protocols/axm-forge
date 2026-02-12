# Interpret Results

## AuditResult Object

Every audit returns an `AuditResult` with these properties:

| Property | Type | Description |
|---|---|---|
| `checks` | `list[CheckResult]` | Individual check results |
| `success` | `bool` | `True` if all checks passed |
| `total` | `int` | Total number of checks |
| `failed` | `int` | Number of failed checks |
| `quality_score` | `float \| None` | Composite score 0–100 |
| `grade` | `str \| None` | Letter grade A–F |

## CheckResult Object

Each individual check returns:

| Property | Type | Description |
|---|---|---|
| `rule_id` | `str` | Unique identifier (`QUALITY_LINT`, etc.) |
| `passed` | `bool` | Whether the check passed |
| `message` | `str` | Human-readable description |
| `severity` | `Severity` | `error`, `warning`, or `info` |
| `details` | `dict \| None` | Tool-specific data (scores, counts) |
| `fix_hint` | `str \| None` | Suggested fix |

## Reporters

### JSON Reporter

```python
from axm_audit.reporters import JsonReporter

reporter = JsonReporter()
print(reporter.render(result))
```

### Markdown Reporter

```python
from axm_audit.reporters import MarkdownReporter

reporter = MarkdownReporter()
print(reporter.render(result))
```

## Severity Levels

| Severity | Effect | Example |
|---|---|---|
| `error` | Blocks audit pass | Missing `pyproject.toml` |
| `warning` | Non-blocking | High complexity function |
| `info` | Informational only | Docstring coverage stats |
