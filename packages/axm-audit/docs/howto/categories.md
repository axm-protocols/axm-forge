# Filter by Category

Focus your audit on specific areas instead of running all checks.

## Available Categories

| Category | Rules | Focus |
|---|---|---|
| `lint` | `LintingRule`, `FormattingRule`, `DiffSizeRule`, `DeadCodeRule` | Code quality (Ruff, git) |
| `type` | `TypeCheckRule` | Type safety (mypy) |
| `complexity` | `ComplexityRule` | Cyclomatic + cognitive complexity (radon CC + complexipy Cog) |
| `security` | `SecurityRule`, `SecurityPatternRule` | Vulnerability detection (Bandit + patterns) |
| `deps` | `DependencyAuditRule`, `DependencyHygieneRule` | Supply chain (pip-audit, deptry) |
| `testing` | `TestCoverageRule` | Coverage enforcement (pytest-cov) |
| `test_quality` | `DuplicateTestsRule`, `FileNamingRule`, `NoPackageSymbolRule`, `PrivateImportsRule`, `PyramidLevelRule`, `TautologyRule` | Test-suite hygiene: pyramid level, duplicates, canonical file naming, package-symbol coverage, private-symbol imports, tautologies |
| `architecture` | `CircularImportRule`, `GodClassRule`, `CouplingMetricRule`, `DuplicationRule` | Structural analysis (AST) |
| `practices` | `DocstringCoverageRule`, `BareExceptRule`, `BlockingIORule`, `MirrorRule`, `AntiMirrorRule`, `EnvCredentialsRule` | Best practices, including direct credential-value reads from the environment |
| `structure` | `PyprojectCompletenessRule`, `TestsPyramidRule` | pyproject.toml completeness; test pyramid layout (unit/integration/e2e + pytest markers) |
| `tooling` | `ToolAvailabilityRule` | CLI tool availability |

`EnvCredentialsRule` reports credential environment variables consumed as values.
It resolves names written literally at the read site, module-level names assigned
a literal string, and `self.<attribute>` reads whose concrete subclasses assign
non-empty literal names—even when the base and subclasses live in different
modules. Each distinct credential name produces its own finding. Runtime-computed
attribute values and other composed names remain unresolved and are ignored.
Boolean-only guards, test modules, non-credential settings, and modules in the
`axm_vault` credential layer are excluded. Remediation points to the axm-vault
credential catalogue exposed through the `axm.credentials` entry-point group.

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

# All rules (32 instances)
rules = get_rules_for_category(None)

# Single category
rules = get_rules_for_category("lint")

# Quick mode (lint + type only)
rules = get_rules_for_category(None, quick=True)

for rule in rules:
    print(f"{type(rule).__name__}: {rule.rule_id}")
```
