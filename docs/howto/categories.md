# Filter by Category

Focus your audit on specific areas instead of running all checks.

## Available Categories

| Category | Rules | Focus |
|---|---|---|
| `quality` | `LintingRule`, `TypeCheckRule`, `ComplexityRule` | Code quality (Ruff, MyPy, Radon) |
| `architecture` | `CircularImportRule`, `GodClassRule`, `CouplingMetricRule` | Structural analysis (AST) |
| `practice` | `DocstringCoverageRule`, `BareExceptRule`, `SecurityPatternRule` | Best practices |
| `structure` | `FileExistsRule`, `DirectoryExistsRule` | Project layout |

## Filter to One Category

```python
from pathlib import Path
from axm_audit import audit_project

# Quality checks only
result = audit_project(Path("."), category="quality")

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

## Python API

```python
for rule in get_rules_for_category("practice"):
    print(f"{type(rule).__name__}: {rule.rule_id}")
```
