# Use MCP or the generic AXM CLI

Install `axm-anvil` in the environment running `axm-mcp` or the `axm` dispatcher. Discovery uses the `axm.tools` entry points; installing into an unrelated environment does not add tools to an already running server. See the [server setup guide](https://forge.axm-protocols.io/mcp/tutorials/quickstart/).

| Registered tool | Operation | Implementation |
|---|---|---|
| `anvil_move` | Move into an existing module | `axm_anvil.tools.move:MoveTool` |
| `anvil_rename` | Rename within the defining module | `axm_anvil.tools.rename:RenameTool` |
| `anvil_extract` | Create a destination if absent, then move | `axm_anvil.tools.extract:ExtractTool` |

These are AXMTools, not CLI commands translated into MCP. In façade mode call `axm_call` with the registered name and an arguments object. For example:

```json
{
  "name": "anvil_move",
  "arguments": {
    "path": "/project",
    "from_file": "src/mylib/models.py",
    "to_file": "src/mylib/services.py",
    "symbols": "UserService",
    "check": true,
    "strict": true
  }
}
```

The root and files above are illustrative. Use a root containing the callers you want rewritten. The façade renders compact text; direct `AXMTool.execute()` returns a structured `ToolResult`. See [results and errors](../reference/contracts.md).

## Rename in place

```bash
axm anvil_rename --path /project --file src/mylib/models.py \
    --old OldName --new NewName --dry-run --strict --json-output
```

For several names, replace `--old`/`--new` with `--mapping '{"Old": "New"}'`. Mapping takes precedence. Review the preview, then remove `--dry-run` to apply. Rename does not discover bare module-attribute callers and has lexical limitations: inspect [rewriting boundaries](../explanation/limits.md#static-rewriting-has-boundaries).

## Extract into a module

```bash
axm anvil_extract --path /project --from-file src/mylib/models.py \
    --to-file src/mylib/value_objects.py --symbols Money,Currency \
    --dry-run --strict --json-output
```

The preview creates and cleans up a missing target scaffold. Apply by removing `--dry-run`; parent directories are created, but `__init__.py` files are not. An existing target is accepted unless it collides. No `check` or `reexport` option is exposed for extract. Do not pass unsupported kwargs: wrappers can ignore them.

## Move through the same dispatcher

```bash
axm anvil_move --path /project --from-file src/mylib/models.py \
    --to-file src/mylib/services.py --symbols UserService --check --strict --json-output
```

`--json-output` prints data, not the ToolResult envelope; failures print an error and exit non-zero. The dedicated `axm-anvil` binary exposes only `move`. For all input defaults and output limitations, see [contracts](../reference/contracts.md) and the [CLI reference](../reference/cli.md).
