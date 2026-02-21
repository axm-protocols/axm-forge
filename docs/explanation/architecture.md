# Architecture

## Overview

`axm-audit` follows a layered architecture with clear separation of concerns:

```mermaid
graph TD
    subgraph "Public API"
        CLI["CLI (cyclopts)"]
        AuditFn["audit_project(path)"]
    end

    subgraph "Auditor"
        Rules["get_rules_for_category()"]
    end

    subgraph "Rule Categories"
        Quality["Quality Rules"]
        Security["Security Rules"]
        Deps["Dependency Rules"]
        Testing["Testing Rules"]
        Arch["Architecture Rules"]
        Practice["Practice Rules"]
        Structure["Structure Rules"]
        Tooling["Tooling Rules"]
    end

    subgraph "Runner"
        RunInProject["run_in_project()"]
    end

    subgraph "Tools"
        Ruff["Ruff"]
        MyPy["mypy"]
        Radon["radon"]
        Bandit["Bandit"]
        PipAudit["pip-audit"]
        Deptry["deptry"]
        PytestCov["pytest-cov"]
        AST["ast module"]
        Tomllib["tomllib"]
    end

    subgraph "Output"
        Result["AuditResult"]
        Formatters["format_report / format_json"]
        Reporters["JsonReporter / MarkdownReporter"]
    end

    CLI --> AuditFn
    AuditFn --> Rules
    Rules --> Quality
    Rules --> Security
    Rules --> Deps
    Rules --> Testing
    Rules --> Arch
    Rules --> Practice
    Rules --> Structure
    Rules --> Tooling
    Quality --> RunInProject
    Security --> RunInProject
    Deps --> RunInProject
    Testing --> RunInProject
    RunInProject --> Ruff
    RunInProject --> MyPy
    RunInProject --> Bandit
    RunInProject --> PipAudit
    RunInProject --> Deptry
    RunInProject --> PytestCov
    Quality -.-> Radon
    Arch --> AST
    Practice --> AST
    Structure --> Tomllib
    Quality --> Result
    Security --> Result
    Deps --> Result
    Testing --> Result
    Arch --> Result
    Practice --> Result
    Structure --> Result
    Tooling --> Result
    Result --> Formatters
    Result --> Reporters
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
| `quality` | `LintingRule`, `FormattingRule`, `TypeCheckRule`, `ComplexityRule` | 4 |
| `security` | `SecurityRule` | 1 |
| `dependencies` | `DependencyAuditRule`, `DependencyHygieneRule` | 2 |
| `testing` | `TestCoverageRule` | 1 |
| `architecture` | `CircularImportRule`, `GodClassRule`, `CouplingMetricRule` | 3 |
| `practice` | `DocstringCoverageRule`, `BareExceptRule`, `SecurityPatternRule` | 3 |
| `structure` | `PyprojectCompletenessRule` | 1 |
| `tooling` | `ToolAvailabilityRule` | 3 instances |

**Total: 18 rule instances across 8 categories.**

### 3. Tool Integration

All subprocess-based rules use `run_in_project()` from `core/runner.py`, which detects the target project's `.venv/` and executes tools via `uv run --directory` to ensure the correct environment is used.

| Rule | Tool | Integration |
|---|---|---|
| `LintingRule` | Ruff | `run_in_project(["ruff", "check", ...])` |
| `FormattingRule` | Ruff | `run_in_project(["ruff", "format", "--check", ...])` |
| `TypeCheckRule` | MyPy | `run_in_project(["mypy", ...])` |
| `ComplexityRule` | Radon | `radon.complexity.cc_visit(source)` |
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
- **Reporters**: `JsonReporter`, `MarkdownReporter` for rendering `AuditResult`

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
    Auditor-->>CLI: list[ProjectRule] (18 rules)
    loop For each rule
        CLI->>Rules: rule.check(project_path)
        Rules->>Tools: Ruff / MyPy / Radon / Bandit / etc.
        Tools-->>Rules: raw output
        Rules-->>CLI: CheckResult
    end
    CLI-->>User: AuditResult (score, grade, checks)
```
