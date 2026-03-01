# Reserve a Package Name

Reserve a package name on PyPI before your project is ready for release.

## Prerequisites

You need a PyPI API token. `axm-init` resolves it automatically (first match wins):

| Priority | Source |
|---|---|
| 1 | `PYPI_API_TOKEN` environment variable |
| 2 | `~/.pypirc` file (`[pypi]` section) |
| 3 | Interactive prompt (saved to `~/.pypirc` for next time) |

!!! tip "First-time setup"
    On first run without a token, you'll be prompted once.
    The token is saved to `~/.pypirc` with `0600` permissions — no need to configure again.

## Reserve

```bash
axm-init reserve my-package-name
```

This publishes a minimal placeholder package (`0.0.1.dev0`) to secure the name.

!!! tip "Author defaults"
    If `--author` and `--email` are omitted, `axm-init` reads `git config user.name`
    and `git config user.email` from your local git configuration.
    If neither flag is provided and git config is unavailable, the command exits with
    an error — author and email are **required** to publish valid package metadata.

## Dry Run

```bash
axm-init reserve my-package-name --dry-run
```

Verifies availability without publishing. No token required.

## JSON Output

```bash
axm-init reserve my-package-name --json
```

Returns structured JSON for CI integration. Exits with code 1 and JSON error if no token is configured (no interactive prompt in JSON mode).

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `Name already taken on PyPI` | Package name is already registered | Choose a different name, or check if you own it at `pypi.org/project/<name>/` |
| `Author and email are required` | Neither `--author`/`--email` flags nor `git config` values found | Pass `--author "Name" --email "email@example.com"` explicitly |
| `No PyPI token configured` | None of the 3 token sources returned a value | Set `PYPI_API_TOKEN` env var or run interactively to be prompted |
| `Build failed` | Package build error (rare) | Check that `uv` and `hatchling` are installed: `uv pip install hatchling` |
