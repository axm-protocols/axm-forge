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
| **LOW** | 0–1 callers, no re-exports |
| **MEDIUM** | 2–4 callers or 1+ affected modules |
| **HIGH** | 5+ callers, re-exported, or many affected modules |

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
  "reexports": ["mylib", "core"]
}
```

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
