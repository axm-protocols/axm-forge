# Filter by Category

Focus your audit on specific areas instead of running all checks.

## Available Categories

| Category | Rules | Focus |
|---|---|---|
| `quality` | `LintingRule`, `TypeCheckRule`, `ComplexityRule` | Code quality (Ruff, mypy, radon) |
| `security` | `SecurityRule` | Vulnerability detection (Bandit) |
| `dependencies` | `DependencyAuditRule`, `DependencyHygieneRule` | Supply chain (pip-audit, deptry) |
| `testing` | `TestCoverageRule` | Coverage enforcement (pytest-cov) |
| `architecture` | `CircularImportRule`, `GodClassRule`, `CouplingMetricRule` | Structural analysis (AST) |
| `practice` | `DocstringCoverageRule`, `BareExceptRule`, `SecurityPatternRule` | Best practices |
| `structure` | `FileExistsRule`, `DirectoryExistsRule` | Project layout |
| `tooling` | `ToolAvailabilityRule` | CLI tool availability |

## CLI

```bash
# Filter to one category
axm-audit audit . --category quality
axm-audit audit . --category security
axm-audit audit . --category dependencies
```

## Python API

```python
from pathlib import Path
from axm_audit import audit_project

# Quality checks only
result = audit_project(Path("."), category="quality")

# Security checks only
result = audit_project(Path("."), category="security")

# Quick mode (lint + type only, fastest)
result = audit_project(Path("."), quick=True)
```

## Get Rules Programmatically

```python
from axm_audit import get_rules_for_category

# All rules (20 instances)
rules = get_rules_for_category(None)

# Single category
rules = get_rules_for_category("quality")

# Quick mode (lint + type only)
rules = get_rules_for_category(None, quick=True)

for rule in rules:
    print(f"{type(rule).__name__}: {rule.rule_id}")
```
