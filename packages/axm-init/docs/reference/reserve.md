# Reserve command reference

[CLI index](cli.md)

## `init_reserve` — Reserve Package Name on PyPI

```
axm init_reserve [OPTIONS] NAME
```

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `NAME` | | string | *required* | Package name to reserve |
| `--author` | | string | *git config* | Author name |
| `--email` | | string | *git config* | Author email |
| `--dry-run` | | bool | `False` | Skip actual publish |
| `--json-output` | | bool | `False` | Output as JSON |

**Default resolution for `--author` / `--email`:**
Only when **both** options are omitted, they are resolved from
`git config user.name` / `git config user.email`. If either is supplied,
the caller must supply the other too.
If git config is not available and neither flag is provided, `axm init_reserve` exits
with code 1 and a descriptive error message.

**Validation rules:**

- Empty `--author` or `--email` after git config fallback → exit code 1
- Placeholder values (`John Doe`, `john.doe@example.com`) are rejected by the MCP tool layer

**Token resolution:**

The tool calls `CredentialManager.get_pypi_token()` against the axm-vault
catalog (`PYPI_API_TOKEN` or the `pypi/token` credential). It does not call
`resolve_pypi_token()` and never prompts, including on a TTY. The separate
adapter method supports interactive setup, but is not the reservation path.

**Exit codes:**

- `0` — reservation succeeded (or dry-run completed)
- `1` — reservation failed (missing identity/token, name taken, …)

As with `init_scaffold`, the exit code is authoritative in text and `--json-output`
mode — a failed reservation exits `1` and errors are also emitted on stderr. Successful JSON contains
`package_name`, `version`, and `message`; early failures use `error`.

**Example:**

```bash
axm init_reserve my-cool-package --dry-run
```

```text
init_reserve | ✓ | my-cool-package | v0.0.1.dev0 | Dry run — would reserve 'my-cool-package' on PyPI
```

After a real successful publication, its project page is
`https://pypi.org/project/<package-name>/`. Dry-run still contacts PyPI to
check availability, but neither builds nor publishes a distribution.
