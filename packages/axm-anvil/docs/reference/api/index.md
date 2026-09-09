# Python API

Import the supported surface from `axm_anvil`. The functions perform filesystem I/O; `MovePlan` and `RenamePlan` are dataclasses. Use [operation contracts](../contracts.md) for defaults, path resolution, results and errors, and [limits](../../explanation/limits.md) for caveats where generated docstrings are broader than current guarantees.

```python
from axm_anvil import MovePlan, move_symbols

# Existing illustrative files; preview only.
plan: MovePlan = move_symbols(
    "src/mylib/models.py", "src/mylib/services.py", ["UserService"],
    dry_run=True, strict=True,
)
print(plan.source_text_new)
print(plan.target_text_new)
print(plan.warnings)
```

`__version__` is the build-generated version string. Tool classes return `ToolResult`; core functions return plans or raise. `SIDE_EFFECT_DECORATORS` and helper record types are internal, not root exports. Some plan fields expose these internal record types; treat their documented fields as inspection data rather than importing internal constructors.

::: axm_anvil
    options:
      members:
        - MoveTool
        - ExtractTool
        - RenameTool
        - move_symbols
        - extract_symbols
        - rename_symbols
        - MovePlan
        - RenamePlan
        - ImportCycleError
        - MovePathError
        - MoveValidationError
        - OverloadPartialMoveError
        - SharedHelpersError
        - SymbolAlreadyExistsError
        - SymbolNotFoundError
      show_root_heading: true
      show_if_no_docstring: true
