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

    subgraph "Tools"
        Ruff["Ruff"]
        MyPy["mypy.api"]
        Radon["radon"]
        Bandit["Bandit"]
        PipAudit["pip-audit"]
        Deptry["deptry"]
        PytestCov["pytest-cov"]
        AST["ast module"]
        FS["pathlib"]
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
    Quality --> Ruff
    Quality --> MyPy
    Quality --> Radon
    Security --> Bandit
    Deps --> PipAudit
    Deps --> Deptry
    Testing --> PytestCov
    Arch --> AST
    Practice --> AST
    Structure --> FS
    Tooling --> FS
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
| `quality` | `LintingRule`, `TypeCheckRule`, `ComplexityRule` | 3 |
| `security` | `SecurityRule` | 1 |
| `dependencies` | `DependencyAuditRule`, `DependencyHygieneRule` | 2 |
| `testing` | `TestCoverageRule` | 1 |
| `architecture` | `CircularImportRule`, `GodClassRule`, `CouplingMetricRule` | 3 |
| `practice` | `DocstringCoverageRule`, `BareExceptRule`, `SecurityPatternRule` | 3 |
| `structure` | `PyprojectCompletenessRule` | 1 |
| `tooling` | `ToolAvailabilityRule` | 3 instances |

**Total: 17 rule instances across 8 categories.**

### 3. Tool Integration

Each rule wraps an external tool using Python APIs where possible:

| Rule | Tool | Integration |
|---|---|---|
| `LintingRule` | Ruff | `subprocess.run([sys.executable, "-m", "ruff", ...])` |
| `TypeCheckRule` | MyPy | `mypy.api.run(["--output", "json", ...])` |
| `ComplexityRule` | Radon | `radon.complexity.cc_visit(source)` |
| `SecurityRule` | Bandit | `subprocess.run(["bandit", "-r", "-f", "json", ...])` |
| `DependencyAuditRule` | pip-audit | `subprocess.run([..., "-m", "pip_audit", ...])` |
| `DependencyHygieneRule` | deptry | `subprocess.run([..., "-m", "deptry", ...])` |
| `TestCoverageRule` | pytest-cov | `subprocess.run([..., "-m", "pytest", "--cov", ...])` |
| Architecture rules | Python `ast` | Direct AST parsing |
| Structure rules | `tomllib` | TOML parsing |
| `ToolAvailabilityRule` | `shutil.which` | PATH lookup |

### 4. Scoring

6-category weighted composite (see [Scoring & Grades](scoring.md)):

| Category | Weight |
|---|---|
| Linting | 20% |
| Type Safety | 20% |
| Complexity | 15% |
| Security | 15% |
| Dependencies | 15% |
| Testing | 15% |

### 5. Models

`AuditResult`, `CheckResult`, `Severity` — Pydantic models with `extra = "forbid"` for strict validation.

### 6. Output

- **Formatters**: `format_report()` (human-readable), `format_json()` (machine-readable)
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
    Auditor-->>CLI: list[ProjectRule] (17 rules)
    loop For each rule
        CLI->>Rules: rule.check(project_path)
        Rules->>Tools: Ruff / MyPy / Radon / Bandit / etc.
        Tools-->>Rules: raw output
        Rules-->>CLI: CheckResult
    end
    CLI-->>User: AuditResult (score, grade, checks)
```
