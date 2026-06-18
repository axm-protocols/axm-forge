# Architecture

## Overview

`axm-audit` follows a layered architecture with clear separation of concerns:

```mermaid
graph TB
    API["CLI / audit_project()"] --> Auditor["get_rules_for_category()"]
    Auditor --> Rules["29 rule classes · 31 instances · 11 Categories"]
    Rules -->|subprocess| Runner["run_in_project()"]
    Rules -->|direct| AST["ast · radon · tomllib"]
    Runner --> Tools["Ruff · mypy · Bandit\npip-audit · deptry · pytest-cov"]
    Hooks["AutofixHook"] -->|subprocess| Runner
    Rules --> Result["AuditResult"]
    Result --> Fmt["format_report · format_json · format_agent"]
```

## Layers

### 1. Public API

- **CLI** — `axm-audit audit .` via cyclopts
- **`audit_project()`** — Python entry point
- **`get_rules_for_category()`** — Get rule instances, optionally filtered

Both return typed Pydantic models for safe agent consumption.

#### Workspace dispatch & concurrency

`audit_project()` detects a multi-package workspace (via
`iter_workspace_packages()`) and dispatches to an internal workspace
auditor that audits each member concurrently with a **bounded
`ThreadPoolExecutor`** (outer pool width capped at
`min(len(packages), os.cpu_count())` to avoid oversubscribing the
per-package inner rule pool). The aggregation is **deterministic**: results
are re-ordered back to the input package order before the worst-of-N merge,
so the rendered output never depends on completion order. Each package keeps
its **own isolated `ASTCache`** — the contextvar-scoped cache is set and
reset *inside* each worker's `audit_project()` call, so the executor
introduces no cross-package cache contention. A failure in one package is
**isolated** as a synthetic `WORKSPACE_PACKAGE_ERROR` failing check and never
aborts the audit of the other packages.

### 2. Rule Engine

`get_rules_for_category()` returns rule instances from the auto-discovery registry (populated by `@register_rule` decorators):

| Category | Rules | Count |
|---|---|---|
| `lint` | `LintingRule`, `FormattingRule`, `DiffSizeRule`, `DeadCodeRule` | 4 |
| `type` | `TypeCheckRule` | 1 |
| `complexity` | `ComplexityRule` | 1 |
| `security` | `SecurityRule`, `SecurityPatternRule` | 2 |
| `deps` | `DependencyAuditRule`, `DependencyHygieneRule` | 2 |
| `testing` | `TestCoverageRule` | 1 |
| `test_quality` | `DuplicateTestsRule`, `FileNamingRule`, `NoPackageSymbolRule`, `PrivateImportsRule`, `PyramidLevelRule`, `TautologyRule` | 6 |
| `architecture` | `CircularImportRule`, `GodClassRule`, `CouplingMetricRule`, `DuplicationRule` | 4 |
| `practices` | `MirrorRule`, `AntiMirrorRule`, `BareExceptRule`, `BlockingIORule`, `DocstringCoverageRule` | 5 |
| `structure` | `TestsPyramidRule`, `PyprojectCompletenessRule` | 2 |
| `tooling` | `ToolAvailabilityRule` | 1 |

**Total: 30 rule classes across 11 categories** (9 scored — see [Scoring & Grades](scoring.md) — plus `structure` and `tooling`, which emit findings but are not scored). `get_rules_for_category(None)` returns **32 instances**: `ToolAvailabilityRule.get_instances()` yields one instance per required tool (`ruff`, `mypy`, `uv`), so its single class expands to 3 instances.

### 3. Tool Integration

All subprocess-based rules use `run_in_project()` from `core/runner.py`, which detects the target project's `.venv/` and executes tools via `uv run --directory` to ensure the correct environment is used. Most rules pass `with_packages=[...]` to inject audit dependencies (ruff, bandit, etc.) at runtime — the target project does **not** need these tools in its own environment. **Exception:** `TypeCheckRule` does **not** inject mypy — it uses the project's own mypy from the venv, ensuring the same type-stub availability and configuration as the project's commit hooks. All subprocess calls have a **300-second timeout** (configurable) — on timeout with `check=False` (the default), a synthetic result with `returncode=124` is returned to prevent indefinite hangs; with `check=True`, the `TimeoutExpired` is re-raised so callers that opted into fail-on-error are never handed a result they could mistake for a real one. To make that timeout effective, the child is launched in its **own process group** (`start_new_session=True` on POSIX, `CREATE_NEW_PROCESS_GROUP` on Windows) and, on timeout, the **whole group is killed** (`os.killpg(..., SIGKILL)`) — so a `uv run` wrapper *and* every process it forked (the inner `python`, worker threads, …) are reaped together. Killing only the direct child would leave a long-running grandchild (e.g. a `torch`-loading worker) orphaned and the audit effectively hung; the group kill prevents that. The output contract is unchanged regardless of platform. A subprocess exit is interpreted in **one place** — `interpret_process(result)` in `core/runner.py` returns a `ProcessVerdict` (`CLEAN` for rc 0, `ISSUES` for an expected non-zero exit carrying findings, `ENV_FAILURE` for rc ∈ `{2, 124}` or a timeout). This is the single source of truth for the env-failure returncode set: both `LintingRule` and `TypeCheckRule` route their env-failure decision through it, so an env-failure or timeout always **fails loud** (`passed=False`, `ERROR`, capped score) and never scores a green 100 off empty output. The **coverage run is the exception**: because it executes the full suite under instrumentation, `run_tests()` passes an explicit, more generous **900-second timeout**, and `TestCoverageRule` surfaces a timeout (`returncode=124`) as an explicit *"coverage not measured"* failure rather than parsing a fabricated coverage percentage from the truncated report.

| Rule | Tool | Integration |
|---|---|---|
| `LintingRule` | Ruff | `run_in_project(["ruff", "check", ...])` |
| `FormattingRule` | Ruff | `run_in_project(["ruff", "format", "--check", ...])` |
| `TypeCheckRule` | MyPy | `run_in_project(["mypy", ...])` |
| `ComplexityRule` | Radon | `radon.complexity.cc_visit(source)` (fallback: `radon cc --json` subprocess) |
| `SecurityRule` | Bandit | `run_in_project(["bandit", ...])` |
| `DependencyAuditRule` | pip-audit | `run_in_project(["pip-audit", ...])` |
| `DependencyHygieneRule` | deptry | `run_in_project(["deptry", ...])` |
| `TestCoverageRule` | pytest-cov | `run_tests()` via `test_runner.py` (collects failures + coverage; skips coverage when `files` is specified; `mode` param accepted for backward compat but ignored; runs with a 900s timeout and reports an explicit *"coverage not measured"* failure on timeout instead of a partial coverage %) |
| Architecture rules | Python `ast` | Direct AST parsing |
| Structure rules | `tomllib` | TOML parsing |
| `ToolAvailabilityRule` | `shutil.which` | PATH lookup |

### 4. Hooks

Pre-gate hooks run before quality evaluation to auto-fix common issues:

| Hook | Commands | Behavior |
|---|---|---|
| `AutofixHook` | `ruff check --fix .`, `ruff format .` | Registered as `audit:autofix` in the `axm.hooks` entry-point group. Runs via `run_in_project()`. Returns `HookResult.ok(fixed=N)` with fix count parsed from ruff stdout. Skips gracefully when ruff is missing (`skipped=True`). Tolerates config errors (returncode 2) without failing. |

### 5. Fix System — CST rewriters

The fix subsystem (`core/fix/cst_rewrite.py`) carries two parallel
surfaces over the same libcst primitives. File-level helpers (the
`_prefixed` ones) load with `_cst_load`, transform, then save with
`_cst_save`. In-memory rewriters take a `cst.Module` and return a
`cst.Module`, leaving I/O to the caller — useful for composing several
edits without redundant parse/serialize round-trips.

| In-memory rewriter | File-level counterpart | Operation |
|---|---|---|
| `flatten_class(module, class_name)` | `_flatten_class_to_top_level` | Promote test methods of `class_name` to module top level, lifting pytest marks |
| `rename_function(module, old, new)` | `_rename_name_in_module` | Rename a top-level function, its references, and matching parametrize string literals |
| `delete_function(module, name)` | `_delete_function_from_source` | Drop a top-level function while preserving adjacent blank-line spacing |
| `patch_file_depth(module, delta)` | `_patch_file_dunder_depth` | Adjust `Path(__file__).parents[N]` subscripts after a directory move |
| `dedupe_imports(module)` | `_dedupe_imports_cst` | Collapse duplicate `import` / `from … import` statements |
| `backfill_import(module, mapping)` | `_insert_imports_cst` | Insert `from {mod} import {name}` entries (idempotent, post-`__future__`) |

Import resolution is backed by a project-wide cache:
`_resolve_import_for_symbol(project_path, symbol)` returns a fresh
`ast.ImportFrom` statement that brings `symbol` into scope, building
the index lazily via `_build_project_symbol_index` and caching it in
`_PROJECT_IMPORT_INDEX_CACHE`. Call `_invalidate_import_index(project_path)`
after mutating the file tree so the next lookup rebuilds.

Layout & move (`core/fix/layout_and_move.py`) wraps axm-anvil's
`move_symbols` with collision detection so the pipeline can reshape
the test tree without losing fixtures or shadowing conftests:

| Symbol | Stage | Purpose |
|---|---|---|
| `relocate_non_canonical_tiers` | 0.5 | Move legacy `tests/<non-canonical>/test_*.py` into `tests/integration/` so RELOCATE only sees canonical tiers. `tests/fixtures/` is excluded (static corpora, not tests) |
| `flatten_tier_layout` | 1.5 | Collapse nested `tests/integration/<sub>/` and `tests/e2e/<sub>/` to flat layout, renaming on collision |
| `_safe_move_units` | per-op | Wrap `move_symbols` with collision dedup/rename, helper-body conflict resolution, conftest-shadow guards, marker-fixture follow-up |
| `_resolve_helper_conflicts` | per-op | Rename source helpers whose body diverges from a same-named helper in target (or shadows conftest) before anvil runs |
| `_resolve_conftest_shadowing` | per-op | Rename target-local helpers that would shadow conftest fixtures the moved tests depend on |

Stage executors (`core/fix/stages_execute.py`) apply the plan: one
function per `FileOp.kind` (`_execute_flatten`, `_execute_relocate`,
`_execute_rename`, `_execute_split`, `_execute_merge`) dispatched by
`execute(ops, project_path)`. The plan itself is a list of `FileOp`
records (`core/fix/models.py`) — each carries `kind`, `source`,
`target` (a single `Path` for non-split ops, `list[Path]` for SPLIT),
`rationale`, `source_rule`, and an optional `split_map` for SPLIT
routing.

The orchestrator (`core/fix/pipeline.py`) exposes `run(project_path,
*, apply, rules) -> PipelineReport`. In `apply=True` mode it iterates
RELOCATE → SPLIT → MERGE → RENAME inside a fixed-point loop capped at
`MAX_ITERATIONS = 6` (re-classification cascade — see the
`MAX_ITERATIONS` docstring); dry-run takes a single pass. After
convergence, two post-pipeline polish steps run (apply-mode only):

| Step | Module | Purpose |
|---|---|---|
| `_extract_shared_helpers` | `core/fix/extract_helpers.py` | Promote helpers/fixtures duplicated across a tier into `tests/<tier>/_helpers.py`. Iterates per-tier until fixed-point (capped at `_EXTRACT_MAX_ITERS = 10`) so promoting helper A can expose helper B. |
| `_ruff_format_tests` | `core/fix/pipeline.py` | Idempotent `ruff format` + `ruff check --fix-only --select F401,I001,UP034` over `tests/`. Failures degrade to warnings — polish never aborts a successful apply. |

`PipelineReport` aggregates the result: `ops` (every planned mutation
across iterations), `unfixable` (findings the pipeline declined),
`applied` (dry-run vs. applied), `warnings` (per-stage + polish
messages), and `iterations` (passes until convergence; 1 in dry-run).

Pipeline invariants (idempotence, parity, convergence, monotonicity,
tree-diff against an expected layout) are validated by the integration
tests under `tests/integration/` (e.g. `test_corpus_loader.py`,
`test_pipeline__run.py`, `test_max_iterations__run.py`) over the [fix
corpus](glossary.md#concepts) — six synthetic mini-packages
(`relocate_only`, `split_only`, `merge_only`, `rename_only`,
`flatten_only`, `mixed`) under `tests/fixtures/fix_corpus/`, each shipping
a paired `input/` and `expected/` tree, consumed via the
`fix_corpus_case(name)` factory defined in the corpus `conftest.py`.

### 6. Scoring

9-category weighted composite (see [Scoring & Grades](scoring.md)). The
`structure` and `tooling` categories emit findings but are not scored:

| Category | Weight |
|---|---|
| Linting | 15% |
| Type Safety | 15% |
| Complexity | 15% |
| Security | 10% |
| Dependencies | 10% |
| Testing | 10% |
| Test Quality | 10% |
| Architecture | 10% |
| Practices | 5% |

### 7. Models

`AuditResult`, `CheckResult`, `Severity` — Pydantic models with `extra = "forbid"` for strict validation.

### 8. Output

- **Formatters**: `format_report()` (human-readable), `format_json()` (machine-readable), `format_agent()` (agent-optimized), `format_agent_text()` (compact text for LLM consumption). `format_agent` uses `_has_actionable_detail()` to promote passing checks with non-empty list-valued detail keys (e.g. `missing`, `top_offenders`) from summary strings to full dicts. `format_agent_text` consumes the dict from `format_agent` and renders a minimal text representation with `✓`/`✗` lines, achieving ~55-60% token savings.

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
    Auditor-->>CLI: list[ProjectRule]
    loop For each rule
        CLI->>Rules: rule.check(project_path)
        Rules->>Tools: Ruff / MyPy / Radon / Bandit / etc.
        Tools-->>Rules: raw output
        Rules-->>CLI: CheckResult
    end
    CLI-->>User: AuditResult (score, grade, checks)
```
