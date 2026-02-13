# Interpret Results

## AuditResult Object

Every audit returns an `AuditResult` with these properties:

| Property | Type | Description |
|---|---|---|
| `checks` | `list[CheckResult]` | Individual check results |
| `success` | `bool` | `True` if all checks passed |
| `total` | `int` | Total number of checks |
| `failed` | `int` | Number of failed checks |
| `quality_score` | `float \| None` | Composite score 0–100 (8-category weighted) |
| `grade` | `str \| None` | Letter grade A–F |

## CheckResult Object

Each individual check returns:

| Property | Type | Description |
|---|---|---|
| `rule_id` | `str` | Unique identifier (`QUALITY_LINT`, `DEPS_AUDIT`, etc.) |
| `passed` | `bool` | Whether the check passed |
| `message` | `str` | Human-readable description |
| `severity` | `Severity` | `error`, `warning`, or `info` |
| `details` | `dict \| None` | Tool-specific data (scores, counts) |
| `fix_hint` | `str \| None` | Suggested fix |

## Formatters

### Human-Readable Report

```python
from axm_audit.formatters import format_report

print(format_report(result))
```

### JSON Output

```python
from axm_audit.formatters import format_json
import json

data = format_json(result)
print(json.dumps(data, indent=2))
```

### Agent Output

`format_agent` minimizes tokens for AI agent consumption. Passed checks are compact strings — unless they carry actionable detail (e.g. missing docstrings), in which case they become dicts with `details` and `fix_hint`:

```python
from axm_audit.formatters import format_agent

data = format_agent(result)
```

Example output structure:

```json
{
  "score": 85.0,
  "grade": "B",
  "passed": [
    "QUALITY_LINT: Lint score: 100/100 (0 issues)",
    {
      "rule_id": "PRACTICE_DOCSTRING",
      "message": "Docstring coverage: 95% (19/20)",
      "details": {"coverage": 0.95, "missing": ["module.py:func"]},
      "fix_hint": "Add docstrings to public functions"
    }
  ],
  "failed": [
    {
      "rule_id": "QUALITY_TYPE",
      "message": "Type score: 70/100 (6 errors)",
      "details": {"score": 70, "error_count": 6},
      "fix_hint": "Run: mypy src/"
    }
  ]
}
```

## Reporters (Legacy)

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

## Scoring

The `quality_score` is computed from 8 weighted categories:

| Category | Weight |
|---|---|
| Linting (Ruff) | 20% |
| Type Safety (mypy) | 15% |
| Complexity (radon) | 15% |
| Security (Bandit) | 10% |
| Dependencies (pip-audit + deptry) | 10% |
| Testing (pytest-cov) | 15% |
| Architecture (AST analysis) | 10% |
| Practices (AST analysis) | 5% |

For details, see [Scoring & Grades](../explanation/scoring.md).

## Severity Levels

| Severity | Effect | Example |
|---|---|---|
| `error` | Blocks audit pass | Missing `pyproject.toml` |
| `warning` | Non-blocking | High complexity function |
| `info` | Informational only | Docstring coverage stats |
