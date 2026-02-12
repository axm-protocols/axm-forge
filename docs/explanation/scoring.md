# Scoring & Grades

## Composite Quality Score

The quality score is a **weighted average** across the 3 quality layers:

| Layer | Tool | Weight |
|---|---|---|
| Linting | Ruff | **40%** |
| Type Checking | MyPy | **35%** |
| Complexity | Radon | **25%** |

Each layer produces a score from 0 to 100. The composite score is:

```
score = lint × 0.40 + type × 0.35 + complexity × 0.25
```

!!! note "Quality score vs. audit checks"
    The `quality_score` tracks code quality tools only. Other rule categories
    (structure, architecture, practice) produce `CheckResult` pass/fail entries
    but do not contribute to the composite score.

## Layer Scoring

### Lint Score

```
score = max(0, 100 − issue_count × 2)
```

Pass threshold: ≥ 80 (≤ 10 issues).

### Type Score

```
score = max(0, 100 − error_count × 5)
```

Pass threshold: ≥ 80 (≤ 4 errors).

### Complexity Score

```
score = max(0, 100 − high_complexity_count × 10)
```

High complexity = cyclomatic complexity ≥ 10. Pass threshold: ≥ 80 (≤ 2 complex functions).

## Grading Scale

| Grade | Score | Meaning |
|---|---|---|
| **A** | ≥ 90 | Excellent — production-ready |
| **B** | ≥ 80 | Good — minor issues |
| **C** | ≥ 70 | Acceptable — needs attention |
| **D** | ≥ 60 | Poor — significant issues |
| **F** | < 60 | Failing — critical problems |

## Severity Levels

Each individual check carries a severity:

| Severity | Effect | Example |
|---|---|---|
| `error` | Blocks audit pass | Missing `pyproject.toml` |
| `warning` | Non-blocking | High complexity function |
| `info` | Informational only | Docstring coverage stats |

## Type Safety

All results use Pydantic models (`AuditResult`, `CheckResult`, `Severity`) with `extra = "forbid"` for strict validation — safe for both human and agent consumption.
