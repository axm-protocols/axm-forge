# Scoring & Grades

## Composite Quality Score

The quality score is a **weighted average** across the 5 analysis layers:

| Layer | Tool | Weight |
|-------|------|--------|
| Linting | Ruff | **25%** |
| Type Checking | MyPy | **30%** |
| Complexity | Radon | **20%** |
| Security | Bandit | **15%** |
| Structure | — | **10%** |

Each layer produces a score from 0 to 100. The composite score is:

```
score = lint×0.25 + type×0.30 + complexity×0.20 + security×0.15 + structure×0.10
```

## Grading Scale

| Grade | Score | Meaning |
|-------|-------|---------|
| **A** | ≥ 90 | Excellent — production-ready |
| **B** | ≥ 80 | Good — minor issues |
| **C** | ≥ 70 | Acceptable — needs attention |
| **D** | ≥ 60 | Poor — significant issues |
| **F** | < 60 | Failing — critical problems |

## Structure Score

The structure score is a simple pass/fail percentage of structure checks:

- `pyproject.toml` exists
- `README.md` exists
- `src/` directory exists
- `tests/` directory exists

## Severity Levels

Each individual check carries a severity:

| Severity | Effect | Example |
|----------|--------|---------|
| `error` | Blocks audit pass | Missing `pyproject.toml` |
| `warning` | Non-blocking | High complexity function |
| `info` | Informational only | Docstring coverage stats |

## Type Safety

All results use Pydantic models (`AuditResult`, `CheckResult`, `Severity`) with `extra = "forbid"` for strict validation — safe for both human and agent consumption.
