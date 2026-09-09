# AXM CLI Reference

Install `axm-smelt` in the environment running `axm`. With `uv add axm-smelt`,
prefix the commands below with `uv run` unless that environment is activated.
The package registers three commands through the AXM tool registry.

| Command | Purpose | Additional inputs |
|---|---|---|
| `axm smelt` | Compact input | `--strategies`, `--preset` |
| `axm smelt_check` | Estimate savings | None |
| `axm smelt_count` | Count input tokens | `--model` |

All accept `--data`, `--input-path`, and the shared `--json-output` switch.

```bash
axm smelt --help
axm smelt_check --help
axm smelt_count --help
```

## Input and strategies

```bash
printf '{"name": "Alice", "notes": null}\n' | axm smelt
axm smelt --input-path ./payload.json --preset moderate
axm smelt --data '{"a": 1, "b": null}' --strategies '["minify", "drop_nulls"]'
axm smelt_count --data 'hello world' --model o200k_base
```

`--strategies` takes **one JSON array argument**, not a comma-separated string
or repeated flag. The generic CLI JSON-decodes `--data` when possible: a JSON
object becomes parsed data with a compact baseline. For the exact whitespace
and token count of a JSON file, use `--input-path` or stdin, which stay text.
To pass JSON-looking content as a string through `--data`, JSON-encode the
string itself.

Input precedence is nonempty data, explicit file, then non-interactive stdin.
See [input edge cases](contracts.md#axmtool-inputs).

## Output and exit status

The default output is a metrics header followed by compacted text for `smelt`;
it is **not a raw compacted file**. Use structured output to extract the payload:

```bash
axm smelt --input-path ./payload.json --json-output
```

`--json-output` prints the tool's `data` mapping, without a `ToolResult`
envelope. Key sets are listed in the [tool contract](contracts.md#toolresult-data).
On a tool failure, the diagnostic goes to stderr and exit status is 1;
malformed JSON for `--strategies` exits 2. CLI parsing errors are also nonzero.
Always check status before consuming stdout (JSON mode can print `{}` on failure).

Commands read inputs and write stdout/stderr; they do not overwrite input files.
See [saving compacted text from Python](../howto/compact.md#save-only-the-compacted-text).
