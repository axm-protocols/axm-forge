# CLI reference

The `axm` command discovers the three `axm.tools` entries shipped by
`axm-init`. There is no separate `axm-init` executable.

| Command | Contract |
|---|---|
| [`axm init_scaffold`](scaffold.md) | Project, research and protocol scaffolding |
| [`axm init_check`](check.md) | Context-aware governance checks |
| [`axm init_reserve`](reserve.md) | PyPI placeholder reservation |

```bash
axm --help
axm --version
axm init_scaffold --help
axm init_check --help
axm init_reserve --help
```

`axm --version` reports the shared AXM package version, not the axm-init version.
Its output is a version string (for example `0.8.0`).

Use long parameter names such as `--author` and `--category`. The generated CLI
does not declare the old short aliases (`-a`, `-c`, `-o`, and so on).
Booleans also have negative forms, such as `--no-preview`. The first path or
name argument can be positional; use named options for the remaining arguments.

A tool failure produces exit code 1 and an error on stderr. Parsing failures
may instead exit 2. `--json-output` selects structured stdout; stderr and
the exit status remain separate. Do not assume every error uses the same JSON
shape: consult the command reference.

See [Python entry points](python-api.md) and [MCP usage](../howto/mcp.md).
