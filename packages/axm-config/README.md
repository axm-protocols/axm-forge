<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>axm-config — Non-sensitive runtime configuration for AXM</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-config/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-config/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-config/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-config/"><img src="https://img.shields.io/pypi/v/axm-config" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://forge.axm-protocols.io/axm-config/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

axm-config provides non-sensitive runtime configuration for AXM: environment
overrides, TOML persistence, typed settings and named profiles. Resolution follows
**environment > file > default**.

## Features

- `get`, `get_file`, `set_`, `delete` and `load` provide resolution and model binding.
- Typed accessors share runtime paths, warden settings and inference defaults.
- Execution-policy helpers persist complete backend/model pairs and analysis overrides.
- `config_doctor` reports provenance; `profile_isolation` computes candidate state paths.

<a id="install"></a>

## Installation

Requires Python 3.12 or newer. In a Python project managed by uv:

```bash
uv add axm-config
uv run axm-config --help
```

<a id="start-with-a-non-sensitive-setting"></a>

## Quick Start

Choose an unused profile name for this example:

```bash
AXM_PROFILE=docs-demo uv run axm-config set research.demo timeout 30
AXM_PROFILE=docs-demo uv run axm-config get research.demo timeout
AXM_PROFILE=docs-demo AXM_RESEARCH__DEMO_TIMEOUT=10 uv run axm-config get research.demo timeout
AXM_PROFILE=docs-demo uv run axm-config delete research.demo timeout
```

The two reads print `30`, then `10`: the environment overrides the stored
value. The final command deletes the example key. These commands write to
`~/.axm/profiles/docs-demo/config.toml`; the profile file can remain afterward.
The CLI stores strings; use the Python API for TOML integers and booleans.

## Usage

### CLI and tools

The `axm-config` command exposes `get`, `set`, `delete`, `path` and `doctor`.
Installed AXMTool entry points also expose diagnostics through the generic CLI:

```bash
uv run axm config_doctor --namespace research.demo
uv run axm profile_isolation --profile scratch
```

`config_doctor` reports where settings come from without returning their values.
`profile_isolation` calculates candidate paths; it does not audit the actual
configuration of every consumer. See the [CLI and tool contracts](docs/reference/cli.md).

### Python configuration

Import the public helpers from `axm_config`. Use `get` for raw resolution,
`get_file` to omit environment overrides, and `load(namespace, model)` to bind
settings to a Pydantic model. See [typed consumer configuration](docs/howto/load-a-consumer-config.md)
and the [Python contracts](docs/reference/contracts.md).

### Profiles and persistence limits

An unset or empty `AXM_PROFILE` selects production at `~/.axm/config.toml`.
Each file replacement is atomic; concurrent read-modify-write operations are
**not serialized**. See the [persistence limits](docs/explanation/architecture.md)
before automating writes.

Passwords, tokens and API keys belong in **axm-vault**, not this plaintext store.
`AXM_HOME` is **not a general store override**; see the profile guide.

## Documentation

The [documentation home](docs/index.md) is the MkDocs landing page; this README
is the repository/package introduction.

- [Published documentation](https://forge.axm-protocols.io/axm-config/)
- [Tutorial](docs/tutorials/getting-started.md)
- [Typed consumer configuration](docs/howto/load-a-consumer-config.md)
- [Profiles and isolation limits](docs/howto/profiles.md)
- [Execution policies](docs/howto/execution-policies.md)
- [CLI and tools](docs/reference/cli.md)
- [Python contracts](docs/reference/contracts.md)
- [Persistence and architecture](docs/explanation/architecture.md)

## Development

Part of the [axm-forge workspace](https://github.com/axm-protocols/axm-forge).
From the workspace root:

```bash
uv sync --all-packages --all-groups
uv run --package axm-config --directory packages/axm-config pytest
```

The package test directory is `packages/axm-config/tests_axm_config`.

Build this package's documentation from its directory with
`mkdocs build --strict`, using an environment containing its local installation,
MkDocs Material and mkdocstrings with the Python handler. The package configuration
also works when included by the workspace site.

## License

Licensed under Apache-2.0. See [LICENSE](LICENSE).
