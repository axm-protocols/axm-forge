# Architecture

## Overview

`axm-audit` follows a layered architecture with clear separation of concerns:

```mermaid
graph TB
    API["CLI / audit_project()"] --> Auditor["get_rules_for_category()"]
    Auditor --> Rules["24 Rules · 8 Categories"]
    Rules -->|subprocess| Runner["run_in_project()"]
    Rules -->|direct| AST["ast · radon · tomllib"]
    Runner --> Tools["Ruff · mypy · Bandit\npip-audit · deptry · pytest-cov"]
    Rules --> Result["AuditResult"]
    Result --> Fmt["format_report · format_json · format_agent"]
```

## Layers

### 1. Public API

- **CLI** — `axm-audit audit .` via cyclopts
- **`audit_project()`** — Python entry point
- **`get_rules_for_category()`** — Get rule instances, optionally filtered

Both return typed Pydantic models for safe agent consumption.

### 2. Rule Engine

`get_rules_for_category()` returns rule instances from the `RULES_BY_CATEGORY` registry:

| Category | Rules | Count |
|---|---|---|
| `quality` | `LintingRule`, `FormattingRule`, `TypeCheckRule`, `ComplexityRule`, `DiffSizeRule`, `DeadCodeRule` | 6 |
| `security` | `SecurityRule` | 1 |
| `dependencies` | `DependencyAuditRule`, `DependencyHygieneRule` | 2 |
| `testing` | `TestCoverageRule` | 1 |
| `architecture` | `CircularImportRule`, `GodClassRule`, `CouplingMetricRule`, `DuplicationRule` | 4 |
| `practice` | `DocstringCoverageRule`, `BareExceptRule`, `SecurityPatternRule`, `BlockingIORule`, `LoggingPresenceRule`, `TestMirrorRule` | 6 |
| `structure` | `PyprojectCompletenessRule` | 1 |
| `tooling` | `ToolAvailabilityRule` | 3 instances |

**Total: 24 rule instances across 8 categories.**

### 3. Tool Integration

All subprocess-based rules use `run_in_project()` from `core/runner.py`, which detects the target project's `.venv/` and executes tools via `uv run --directory` to ensure the correct environment is used. All subprocess calls have a **300-second timeout** (configurable) — on timeout, a synthetic result with `returncode=124` is returned to prevent indefinite hangs.

| Rule | Tool | Integration |
|---|---|---|
| `LintingRule` | Ruff | `run_in_project(["ruff", "check", ...])` |
| `FormattingRule` | Ruff | `run_in_project(["ruff", "format", "--check", ...])` |
| `TypeCheckRule` | MyPy | `run_in_project(["mypy", ...])` |
| `ComplexityRule` | Radon | `radon.complexity.cc_visit(source)` (fallback: `radon cc --json` subprocess) |
| `SecurityRule` | Bandit | `run_in_project(["bandit", ...])` |
| `DependencyAuditRule` | pip-audit | `run_in_project(["pip-audit", ...])` |
| `DependencyHygieneRule` | deptry | `run_in_project(["deptry", ...])` |
| `TestCoverageRule` | pytest-cov | `run_in_project(["pytest", "--cov", ...])` |
| Architecture rules | Python `ast` | Direct AST parsing |
| Structure rules | `tomllib` | TOML parsing |
| `ToolAvailabilityRule` | `shutil.which` | PATH lookup |

### 4. Scoring

8-category weighted composite (see [Scoring & Grades](scoring.md)):

| Category | Weight |
|---|---|
| Linting | 20% |
| Type Safety | 15% |
| Complexity | 15% |
| Security | 10% |
| Dependencies | 10% |
| Testing | 15% |
| Architecture | 10% |
| Practices | 5% |

### 5. Models

`AuditResult`, `CheckResult`, `Severity` — Pydantic models with `extra = "forbid"` for strict validation.

### 6. Output

- **Formatters**: `format_report()` (human-readable), `format_json()` (machine-readable), `format_agent()` (agent-optimized)

## Data Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI as CLI / audit_project()
    participant Auditor
    participant Rules
    participant Tools

    User->>CLI: axm-audit audit . / audit_project(Path("."))
    CLI->>Auditor: get_rules_for_category(category)
    Auditor-->>CLI: list[ProjectRule] (24 rules)
    loop For each rule
        CLI->>Rules: rule.check(project_path)
        Rules->>Tools: Ruff / MyPy / Radon / Bandit / etc.
        Tools-->>Rules: raw output
        Rules-->>CLI: CheckResult
    end
    CLI-->>User: AuditResult (score, grade, checks)
```
