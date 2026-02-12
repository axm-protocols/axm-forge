# Architecture

## Overview

`axm-audit` follows a layered architecture with clear separation of concerns:

```mermaid
graph TD
    subgraph "Public API"
        AuditFn["audit_project(path)"]
    end

    subgraph "Auditor"
        Rules["get_rules_for_category()"]
    end

    subgraph "Rule Categories"
        Quality["Quality Rules"]
        Arch["Architecture Rules"]
        Practice["Practice Rules"]
        Structure["Structure Rules"]
    end

    subgraph "Tools"
        Ruff["Ruff (sys.executable)"]
        MyPy["mypy.api.run()"]
        Radon["radon.complexity.cc_visit()"]
        AST["ast module"]
        FS["pathlib"]
    end

    subgraph "Output"
        Result["AuditResult"]
        Reporters["JsonReporter / MarkdownReporter"]
    end

    AuditFn --> Rules
    Rules --> Quality
    Rules --> Arch
    Rules --> Practice
    Rules --> Structure
    Quality --> Ruff
    Quality --> MyPy
    Quality --> Radon
    Arch --> AST
    Practice --> AST
    Structure --> FS
    Quality --> Result
    Arch --> Result
    Practice --> Result
    Structure --> Result
    Result --> Reporters
```

## Layers

### 1. Public API

- **`audit_project()`** — Main entry point (`__init__.py`)
- **`get_rules_for_category()`** — Get rule instances, optionally filtered

Both return typed Pydantic models for safe agent consumption.

### 2. Rule Engine

`get_rules_for_category()` returns rule instances from the `RULES_BY_CATEGORY` registry:

| Category | Rules |
|---|---|
| `quality` | `LintingRule`, `TypeCheckRule`, `ComplexityRule` |
| `architecture` | `CircularImportRule`, `GodClassRule`, `CouplingMetricRule` |
| `practice` | `DocstringCoverageRule`, `BareExceptRule`, `SecurityPatternRule` |
| `structure` | `FileExistsRule`, `DirectoryExistsRule` |

### 3. Tool Integration

Each rule wraps an external tool using Python APIs where possible:

| Rule | Tool | Integration |
|---|---|---|
| `LintingRule` | Ruff | `subprocess.run([sys.executable, "-m", "ruff", ...])` |
| `TypeCheckRule` | MyPy | `mypy.api.run(["--output", "json", ...])` |
| `ComplexityRule` | Radon | `radon.complexity.cc_visit(source)` |
| Architecture rules | Python `ast` | Direct AST parsing |
| Structure rules | `pathlib` | Filesystem checks |

### 4. Models

`AuditResult`, `CheckResult`, `Severity` — Pydantic models with `extra = "forbid"` for strict validation.

### 5. Reporters

`JsonReporter` and `MarkdownReporter` render `AuditResult` for different consumers.

## Data Flow

```mermaid
sequenceDiagram
    participant User
    participant API as audit_project()
    participant Auditor
    participant Rules
    participant Tools

    User->>API: audit_project(Path("."))
    API->>Auditor: get_rules_for_category(category)
    Auditor-->>API: list[ProjectRule]
    loop For each rule
        API->>Rules: rule.check(project_path)
        Rules->>Tools: Ruff / MyPy / Radon / AST
        Tools-->>Rules: raw output
        Rules-->>API: CheckResult
    end
    API-->>User: AuditResult (score, grade, checks)
```
