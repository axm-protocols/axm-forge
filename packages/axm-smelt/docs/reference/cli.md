# AXM CLI Reference

`axm-smelt` no longer installs a standalone executable and the package is not
runnable with `python -m axm_smelt`. The command surface is generated from the
three `axm.tools` entry points, so CLI, MCP, and DAG execution share one
interface declaration.

## Tool commands

| Command | Purpose |
|---|---|
| `axm smelt` | Compact text or structured data |
| `axm smelt_check` | Analyze potential savings without transforming the input |
| `axm smelt_count` | Count input tokens |

Use the generated help for the exact arguments exposed by the installed version:

```bash
axm smelt --help
axm smelt_check --help
axm smelt_count --help
```

The former `compact`, `check`, `count`, and `version` subcommands, along
with their `--file` and `--output` plumbing, are not compatibility aliases.
Provide explicit data, use `--input-path` for a UTF-8 file, or redirect text to
standard input; that is also their precedence order. Output persistence remains
the caller's responsibility.

If the designated path does not exist or its contents are not valid UTF-8, the
command exits with a non-zero status and a diagnostic that names that path.

For structured programmatic calls and result fields, see
[Use via MCP](../howto/mcp.md).

## Python API

The package-level `smelt`, `check`, and `count` functions are unchanged.
Auto-generated API reference is available under
[Python API](../reference/axm_smelt/index.md).
