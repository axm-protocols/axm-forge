# CLI reference

## The `axm` Command

```bash
axm
axm --help
axm --version
axm -V
```

No arguments or root help prints the installed command catalog without loading
tool implementations. Version flags are recognized as the first argument and
print the installed `axm` version. Unknown commands exit with code 2:
the diagnostic goes to stderr and the catalog to stdout.

## Available Commands

`axm` declares its launcher under `project.scripts`; it declares no tool
entry points itself. The current environment supplies the catalog through
`axm.tools`. Do not assume a fixed command count.

For example, after installing `'axm[init]'`:

```bash
axm init_check --help
axm init_check --path . --json-output
```

Use each provider's help for its domain options. Standalone provider binaries
are separate interfaces, not automatically subcommands of this launcher.

## Parameters

Generated tool signatures come from `execute` (or a registered callable).
The adapter drops `self`, a parameter named `kwargs` and variadic
`**kwargs`. Keyword-only parameters are exposed as positional-or-keyword,
so the first parameter can usually be passed either positionally or by name.
Scalar `Annotated[..., cyclopts.Parameter(...)]` metadata is retained;
structured parameters are replaced by JSON-string annotations.

## Non-scalar parameters

Lists, dicts, tuples, sets and other structured annotations, including
Pydantic models, use one JSON token on the command line. This also applies to
optional and `Annotated` wrappers. The wrapper decodes JSON; it does **not**
construct a Pydantic model, tuple or set from the decoded value. The tool owns
any required conversion and domain validation.

For the [example tool](../howto/write-tool.md):

```bash
axm demo_count --labels '["alpha", "beta"]'
```

A purely structured parameter with invalid JSON exits with code 2 before
execution. For a structured union that also admits `str`, including supported
recursive PEP 695 aliases, valid JSON is decoded and other tokens remain
literal text. Thus `null`, `123` or a quoted JSON string is decoded rather
than preserved verbatim.

## Output modes

Generated tool commands use the following default rendering order:

1. If the result failed and has a nonempty error, write it to stderr.
2. If `text` is a string, write it to stdout (even an empty string).
3. Otherwise, render a nonempty `data` dictionary as JSON.
4. With no such data, print the result's string representation, except an
   error-only failure has already been reported on stderr.

The shared `--json-output` instead emits the data dictionary, including
`{}` when empty. It does not emit a `success/data/error` envelope.
Values unsupported by JSON serialization use their string representation.
Check the process exit status in addition to parsing the JSON.

If the tool declares its own `json_output` parameter, the wrapper neither
adds nor intercepts the shared option: the tool owns that flag's behavior.

The wrapper keeps its own failure diagnostics on stderr; it cannot prevent
a provider from printing directly to stdout.

## Exit statuses

| Status | Generated-tool behavior |
|---|---|
| 0 | Normal completion; also root catalog and version |
| 1 | `success=False`, an exception in execution, or generated-tool loading failure |
| 2 | Invalid command usage or invalid JSON for a structured parameter |

Legacy `axm.commands` entries are ignored, including when they share a name
with a tool. Migrate request–response commands to `axm.tools`; standalone
process lifecycle commands belong under `project.scripts`.

## Python API

These launcher helpers live in `axm.cli`, outside the root SDK façade.
`create_app()` eagerly loads the catalog and is intended for introspection
and tests. The installed command uses the lazy `main()` path.

::: axm.cli.create_app
    options:
      skip_local_inventory: true

::: axm.cli.build_command_for_tool
    options:
      skip_local_inventory: true

## Tool Interface

See the [SDK reference](python-api.md) for `AXMTool`, `ToolResult`,
metadata and the node adapter.

## Validation Interface

See [witnesses](witnesses.md) for their separate result contracts.
