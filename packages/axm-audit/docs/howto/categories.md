# Filter by Category

Focus your audit on specific areas instead of running all checks.

## Available Categories

| Category | Rules | Focus |
|---|---|---|
| `lint` | `LintingRule`, `FormattingRule`, `DiffSizeRule`, `DeadCodeRule` | Code quality (Ruff, git) |
| `type` | `TypeCheckRule` | Type safety (mypy) |
| `complexity` | `ComplexityRule` | Cyclomatic complexity (radon) |
| `security` | `SecurityRule`, `SecurityPatternRule` | Vulnerability detection (Bandit + patterns) |
| `deps` | `DependencyAuditRule`, `DependencyHygieneRule` | Supply chain (pip-audit, deptry) |
| `testing` | `TestCoverageRule` | Coverage enforcement (pytest-cov) |
| `test_quality` | _(scaffolded; rules land in follow-up tickets)_ | Test-tree heuristics: pyramid level, tautologies, mock hygiene |
| `architecture` | `CircularImportRule`, `GodClassRule`, `CouplingMetricRule`, `DuplicationRule` | Structural analysis (AST) |
| `practices` | `DocstringCoverageRule`, `BareExceptRule`, `BlockingIORule`, `SecurityPatternRule`, `TestMirrorRule` | Best practices |
| `structure` | `PyprojectCompletenessRule`, `TestsPyramidRule` | pyproject.toml completeness; test pyramid layout (unit/integration/e2e + pytest markers) |
| `tooling` | `ToolAvailabilityRule` | CLI tool availability |

## CLI

```bash
# Filter to one category
axm-audit audit . --category lint
axm-audit audit . --category security
axm-audit audit . --category deps
```

## Python API

```python
from pathlib import Path
from axm_audit import audit_project

# Lint checks only
result = audit_project(Path("."), category="lint")

# Security checks only
result = audit_project(Path("."), category="security")

# Quick mode (lint + type only, fastest)
result = audit_project(Path("."), quick=True)
```

## Get Rules Programmatically

```python
from axm_audit import get_rules_for_category

# All rules (24 instances)
rules = get_rules_for_category(None)

# Single category
rules = get_rules_for_category("lint")

# Quick mode (lint + type only)
rules = get_rules_for_category(None, quick=True)

for rule in rules:
    print(f"{type(rule).__name__}: {rule.rule_id}")
```
