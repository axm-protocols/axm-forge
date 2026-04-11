# Analyze Change Impact

Before refactoring a function, use `impact` to understand the blast radius.

## Basic Usage

```bash
axm-ast impact src/mylib --symbol my_function
```

Output:

```
💥 Impact analysis for 'my_function' — HIGH

  📍 Defined in: core.utils (L42)
  📞 Direct callers (5): cli, core.engine, core.validator
  📄 Affected modules (3): cli, core.engine, core.validator
  🧪 Tests to rerun (4): test_utils, test_engine, test_cli, test_validator
  📦 Re-exported in (2): mylib, core
```

## Understanding the Score

| Score | Criteria |
|---|---|
| **LOW** | 0-1 callers, no re-exports, no coupled files |
| **MEDIUM** | 2-4 callers or 1+ affected modules or coupled files |
| **HIGH** | 5+ callers, re-exported, many affected modules, or many coupled files |

## Find Callers First

For just the call-site list without full impact analysis:

```bash
axm-ast callers src/mylib --symbol my_function
```

```
📞 5 caller(s) of 'my_function':

  cli:89 in main()
    my_function(args)
  core.engine:42 in process()
    my_function(data)
```

## Exclude Test Modules

Use `--exclude-tests` to focus the analysis on production code only, filtering out test modules from callers and affected modules:

```bash
axm-ast impact src/mylib --symbol my_function --exclude-tests
```

This is useful when you want a clean view of production blast radius without test files inflating the caller count or affected module list. Test files are still listed under `test_files` — they are only removed from the callers/affected-modules sections.

## Filter Test Callers

Use `--test-filter` for fine-grained control over which test callers appear in the output:

| Mode | Behavior |
|---|---|
| `none` | Exclude all test callers (same as `--exclude-tests`) |
| `all` | Keep all callers including tests (default) |
| `related` | Keep only tests that **directly** call the symbol |

```bash
# Only show tests that directly exercise the symbol
axm-ast impact src/mylib --symbol my_function --test-filter related
```

The `related` mode is useful for high-impact symbols (e.g., base classes, utility types) that appear in many test files but are only directly tested by a few. It filters out transitive test references to surface the tests most relevant to the change.

!!! note "Precedence"
    If both `--exclude-tests` and `--test-filter` are set, `--test-filter` takes precedence and a warning is emitted.

## Batch Analysis

Analyze multiple symbols at once with `--symbols`:

```bash
axm-ast impact src/mylib --symbols my_function,MyClass
```

### Compact Output

Use `--detail compact` for a condensed markdown table — ideal for MCP tool
responses and quick triage:

```bash
axm-ast impact src/mylib --symbol my_function --detail compact
```

```
| Symbol | Location | Score | Prod | Direct tests | Indirect tests |
|---|---|---|---|---|---|
| my_function | core.utils:42 | HIGH | cli:89, engine:42 | test_utils | test_engine (+1 more) |

Tests: test_utils.py, test_engine.py
```

When combined with `--symbols`, each symbol gets its own row in the table.

## JSON for CI

```bash
axm-ast impact src/mylib --symbol my_function --json
```

```json
{
  "symbol": "my_function",
  "score": "HIGH",
  "definition": {"module": "core.utils", "line": 42, "kind": "function"},
  "callers": [{"module": "cli", "line": 89, "context": "main"}],
  "affected_modules": ["cli", "core.engine", "core.validator"],
  "test_files": ["test_utils.py", "test_engine.py"],
  "reexports": ["mylib", "core"],
  "git_coupled": [
    {"file": "src/mylib/config.py", "strength": 0.75, "co_changes": 6},
    {"file": "src/mylib/schema.py", "strength": 0.45, "co_changes": 4}
  ]
}
```

## Git Change Coupling

`impact` enriches its analysis with **git change coupling** — files that historically co-change with the symbol's file. This reveals hidden dependencies invisible to static analysis (e.g., config files, schemas, docs that always change together).

Formula: `coupling(A, B) = co_changes(A, B) / max(changes(A), changes(B))` over the last 6 months of git history.

Only files with coupling strength ≥ 0.3 **and** ≥ 3 co-changes are included.

```json
{
  "git_coupled": [
    {"file": "src/mylib/config.py", "strength": 0.75, "co_changes": 6}
  ]
}
```

!!! note "Graceful degradation"
    If the project is not in a git repo or uses a shallow clone, `git_coupled` is simply an empty list — no error is raised.

## Import-Based Test Heuristic

When no test files reference a symbol by name (common for dataclasses, config models, or newly added symbols), `impact` falls back to an **import-based heuristic**: it scans `tests/` for files that import the module containing the symbol.

Results appear in a separate key to distinguish them from direct matches:

```json
{
  "test_files": [],
  "test_files_by_import": ["test_models.py", "test_config.py"]
}
```

!!! note "When does the heuristic run?"
    Only when `test_files` is empty **and** the symbol has a known definition. If direct test matches exist, the heuristic is skipped to avoid noise.

## Workspace: Cross-Package Impact

For `uv` workspaces with multiple packages, `impact` automatically performs cross-package analysis:

```bash
axm-ast impact /path/to/workspace --symbol ToolResult
```

```
💥 Impact analysis for 'ToolResult' — HIGH (workspace)

  📍 Defined in: axm::tools.base (L15) [package: axm]
  📞 Direct callers (12): axm_mcp::server, axm_ast::tools.context, ...
  🧪 Tests to rerun (5): test_tools, test_server, ...
  📦 Re-exported in (3): axm, axm_ast, axm_mcp
```

!!! tip "Automatic detection"
    No flag needed — if the path contains a `pyproject.toml` with `[tool.uv.workspace]`, workspace mode activates automatically.

## Workflow: Safe Refactoring

1. **Check impact** before changing a symbol:

    ```bash
    axm-ast impact src/mylib --symbol old_function
    ```

2. **Run only affected tests** after your change:

    ```bash
    pytest tests/test_utils.py tests/test_engine.py
    ```

3. **Verify no callers remain** if removing a symbol:

    ```bash
    axm-ast callers src/mylib --symbol old_function
    ```
