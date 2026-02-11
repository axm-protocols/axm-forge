# Reserve a Package Name

Reserve a package name on PyPI before your project is ready for release.

## Prerequisites

You need a PyPI API token. `axm-init` resolves it automatically:

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
