# Reserve a Package Name

Reserve a package name on PyPI before your project is ready for release.

## Prerequisites

You need a PyPI API token. `axm-init` resolves it automatically (first match wins):

| Priority | Source |
|---|---|
| 1 | axm-vault credentials catalog (`PYPI_API_TOKEN` environment variable or `pypi.token` credential) |
| 2 | Interactive prompt (persisted to the axm-vault credentials catalog) |

!!! tip "First-time setup"
    On first run without a token, you'll be prompted once.
    The token is persisted to the axm-vault credentials catalog for future runs.

## Reserve

```bash
axm init_reserve my-package-name
```

This publishes a minimal placeholder package (`0.0.1.dev0`) to secure the name.

!!! tip "Author defaults"
    If `--author` and `--email` are omitted, `axm-init` reads `git config user.name`
    and `git config user.email` from your local git configuration.
    If neither flag is provided and git config is unavailable, the command exits with
    an error — author and email are **required** to publish valid package metadata.

## Dry Run

```bash
axm init_reserve my-package-name --dry-run
```

Verifies availability without publishing. No token required.

## JSON Output

```bash
axm init_reserve my-package-name --json-output
```

Returns structured JSON for CI integration. Exits with code 1 and JSON error if no token is configured (no interactive prompt in JSON mode).

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `Name already taken on PyPI` | Package name is already registered | Choose a different name, or check if you own it at `pypi.org/project/<name>/` |
| `Author and email are required` | Neither `--author`/`--email` flags nor `git config` values found | Pass `--author "Name" --email "email@example.com"` explicitly |
| `No PyPI token configured` | Neither catalog resolution nor the interactive prompt returned a value | Set `PYPI_API_TOKEN`, configure the axm-vault credential `pypi.token`, or run interactively |
| `Build failed` | Package build error (rare) | Check that `uv` and `hatchling` are installed: `uv pip install hatchling` |
