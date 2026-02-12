# Filter by Category

Focus your audit on specific areas instead of running all checks.

## Available Categories

| Category | Rules | Focus |
|----------|-------|-------|
| `structure` | `FileExistsRule`, `DirectoryExistsRule` | Project layout (pyproject.toml, src/, tests/) |
| `quality` | `LintingRule`, `TypeCheckRule`, `ComplexityRule` | Code quality (Ruff, MyPy, Radon) |
| `security` | `SecurityRule` | Vulnerability scanning (Bandit) |
| `architecture` | `CircularImportRule`, `GodClassRule`, `CouplingMetricRule` | Structural analysis (AST) |
| `practice` | `DocstringCoverageRule`, `BareExceptRule`, `SecurityPatternRule` | Best practices |

## Filter to One Category

```python
from pathlib import Path
from axm_audit import audit_project

# Security checks only
result = audit_project(Path("."), category="security")

# Architecture checks only
result = audit_project(Path("."), category="architecture")
```

## Get Rules Programmatically

```python
from axm_audit import get_rules_for_category

# All rules
rules = get_rules_for_category(None)

# Single category
rules = get_rules_for_category("quality")

# Quick mode (lint + type only)
rules = get_rules_for_category(None, quick=True)
```
