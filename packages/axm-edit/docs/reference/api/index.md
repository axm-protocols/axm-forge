# Python API

## Supported root exports

The root contract is `axm_edit.__all__`: `batch_apply`, `rollback`,
`Edit`, `ReplaceOp`, `CreateOp`, `DeleteOp`, `Operation`,
`BatchResult`, `RollbackResult`, `ValidationError`, and `__version__`.
`ValidationError` is a result-detail model, not the Pydantic exception.

`Operation` is the union of replace/create/delete/rewrite models.
`RewriteOp` participates in that union but is **not re-exported at the root**:
import it from `axm_edit.models.operations`.
Other public-looking core helpers are internal implementation modules,
not additional root contracts.

The [README example](https://github.com/axm-protocols/axm-forge/tree/main/packages/axm-edit)
uses the root API; the [tutorial](../../tutorials/getting-started.md) uses tool classes.
Review the [recovery limits](../../howto/rollback.md) alongside the generated
docstrings: restoration is best-effort and metadata is not snapshotted.

::: axm_edit
    options:
      members:
        - batch_apply
        - rollback
        - Edit
        - ReplaceOp
        - CreateOp
        - DeleteOp
        - Operation
        - BatchResult
        - RollbackResult
        - ValidationError
        - __version__
      show_source: false

`RewriteOp(file: str, content: str, expected_checksum: str)` adds the
`op="rewrite"` discriminator. The checksum is required; see the
[rewrite guide](../../howto/rewrite.md).

## Tool integrations

These module classes are the installed `axm.tools` entry points.
Their `execute` methods return `axm.tools.base.ToolResult`.
Their docstrings are generated from the checkout; where a docstring overstates
a guarantee, the [batch](../batch.md) and
[filesystem](../filesystem.md) contracts describe the implementation:
in particular, process execution uses no implicit shell.

::: axm_edit.tools.batch_edit.BatchEditTool
    options:
      members: [execute]
      show_source: false

::: axm_edit.tools.batch_edit_check.BatchEditCheckTool
    options:
      members: [execute]
      show_source: false

::: axm_edit.tools.batch_rollback.BatchRollbackTool
    options:
      members: [execute]
      show_source: false

::: axm_edit.tools.read_file.ReadFileTool
    options:
      members: [execute]
      show_source: false

::: axm_edit.tools.write_file.WriteFileTool
    options:
      members: [execute]
      show_source: false

::: axm_edit.tools.edit_file.EditFileTool
    options:
      members: [execute]
      show_source: false

::: axm_edit.tools.search_files.SearchFilesTool
    options:
      members: [execute]
      show_source: false

::: axm_edit.tools.list_dir.ListDirTool
    options:
      members: [execute]
      show_source: false

::: axm_edit.tools.file_bytes.FileBytesTool
    options:
      members: [execute]
      show_source: false

::: axm_edit.tools.run_command.RunCommandTool
    options:
      members: [execute]
      show_source: false
