# Reserve a Package Name

Reserve a package name on PyPI before your project is ready for release.

## Prerequisites

You need a PyPI API token. `axm-init` resolves it automatically (first match wins):

| Priority | Source |
|---|---|
| 1 | axm-vault credentials catalog (`PYPI_API_TOKEN` environment variable or `pypi.token` credential) |


The reservation tool never prompts. Configure the catalog credential or
`PYPI_API_TOKEN` before a real publication. The separate adapter method
`resolve_pypi_token()` can prompt and persist credentials, but this tool uses
`get_pypi_token()` only.

## Reserve

```bash
axm init_reserve my-package-name
```

This publishes a minimal placeholder package (`0.0.1.dev0`) to secure the name.

!!! tip "Author defaults"
    If `--author` and `--email` are omitted, `axm-init` reads `git config user.name`
    and `git config user.email` from your local git configuration.
    If only one identity flag is supplied, no git fallback fills the other.
    If neither flag is provided and git config is unavailable, the command exits with
    an error — author and email are **required** to publish valid package metadata.

## Dry Run

```bash
axm init_reserve my-package-name --dry-run
```

Contacts PyPI to verify availability without building or publishing. No token required.

## JSON Output

```bash
axm init_reserve my-package-name --json-output
```

Returns `package_name`, `version`, and `message` on a completed reservation.
Missing identity/token produces exit code 1 and an `error` payload; stderr also
carries the error. There is no interactive prompt in any output mode.

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `Name already taken on PyPI` | Package name is already registered | Choose a different name, or check if you own it at `pypi.org/project/<name>/` |
| `Author and email are required` | Neither `--author`/`--email` flags nor `git config` values found | Pass `--author "Name" --email "email@example.com"` explicitly |
| `No PyPI token configured` | Catalog resolution returned no token | Set `PYPI_API_TOKEN`, configure the axm-vault credential `pypi.token` |
| `Build failed` | Package build error (rare) | Check that `uv` and `hatchling` are installed: `uv pip install hatchling` |
