# Python entry points

The root package exports only `__version__` through `__all__`:

```python
from axm_init import __version__

print(__version__)
```

The operational interface is the three registered AXMTools. Python integrations
can import their defining modules explicitly; these classes are not re-exported
from `axm_init`.

| Import | Operation | Contract |
|---|---|---|
| `axm_init.tools.scaffold.InitScaffoldTool` | `execute(path=".", **named_options)` | [Scaffold parameters and data](scaffold.md) |
| `axm_init.tools.check.InitCheckTool` | `execute(path=".", *, category=None, json_output=False, agent=False, verbose=False)` | [Check data and exit policy](check.md) |
| `axm_init.tools.reserve.InitReserveTool` | `execute(name="", *, author="", email="", dry_run=False, json_output=False)` | [Reservation data](reserve.md) |

`execute` returns a `ToolResult` with `success`, structured `data`, optional
display `text` and `error`. Python callers inspect `success`; the CLI wrapper
translates failure to its process exit status.

## Module interfaces for developers

These module-level interfaces are not part of the root export list.
Use them when extending or testing the package, rather than assuming they are
additional CLI commands.

| Module | Interfaces | Role |
|---|---|---|
| `axm_init.core.checker` | `CheckEngine`, `format_agent`, `format_agent_text`, `format_report`, `format_json`, `resolve_exit_code` | Run and render checks |
| `axm_init.models.check` | `CheckResult`, `CategoryScore`, `ProjectResult`, `Grade` | Weighted outcomes and N/A state |
| `axm_init.models.results` | `ScaffoldResult`, `ReserveResult` | Core operation results |
| `axm_init.core.templates` | `TemplateInfo`, `TemplateType`, `get_template_path` | [Template selection](templates.md) |
| `axm_init.core.framework` | `Framework`, `detect_framework` | Framework selection |
| `axm_init.models.protocol_scaffold` | `ProtocolScaffoldDecl`, component declaration models | [Protocol validation](protocol-scaffold.md) |
| `axm_init.core.protocol_planner` | `plan_protocol_scaffold` | Pure file/metadata planning |
| `axm_init.core.protocol_scaffolder` | `prepare_protocol_request`, `preview_protocol_scaffold`, `build_protocol_scaffold_result` | Validate requests, preview or apply, shape results |

## Declaration models generated from source

::: axm_init.models.protocol_scaffold
