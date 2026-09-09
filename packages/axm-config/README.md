# axm-config

Non-sensitive runtime configuration for AXM: environment overrides, TOML persistence,
typed settings and named profiles. Python 3.12+.

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-config/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-config/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-config/coverage.json" alt="Coverage"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
</p>

## Install

```bash
uv add axm-config
axm-config --help
```

## Start with a non-sensitive setting

```bash
AXM_PROFILE=docs-demo axm-config set research.demo timeout 30
AXM_PROFILE=docs-demo axm-config get research.demo timeout
AXM_PROFILE=docs-demo AXM_RESEARCH__DEMO_TIMEOUT=10 axm-config get research.demo timeout
AXM_PROFILE=docs-demo axm-config delete research.demo timeout
```

These commands write to `~/.axm/profiles/docs-demo/config.toml`. The CLI stores
strings; use the Python API for TOML integers and booleans. Choose an unused
profile name for experiments. An unset or empty `AXM_PROFILE` selects production
at `~/.axm/config.toml`.

- `get`, `get_file`, `set_`, `delete` and `load` provide resolution and model binding.
- Typed accessors share runtime paths, warden settings and inference defaults.
- Execution-policy helpers persist complete backend/model pairs and analysis overrides.
- `config_doctor` reports provenance; `profile_isolation` computes candidate state paths.
- Each file replacement is atomic; concurrent read-modify-write operations are
  **not serialized**. See the documented persistence limits before automating writes.

Passwords, tokens and API keys belong in **axm-vault**, not this plaintext store.
`AXM_HOME` is **not a general store override**; see the profile guide.

## Documentation

The [documentation home](docs/index.md) is the MkDocs landing page; this README
is the repository/package introduction.

- [Tutorial](docs/tutorials/getting-started.md)
- [Typed consumer configuration](docs/howto/load-a-consumer-config.md)
- [Profiles and isolation limits](docs/howto/profiles.md)
- [Execution policies](docs/howto/execution-policies.md)
- [CLI and tools](docs/reference/cli.md)
- [Python contracts](docs/reference/contracts.md)
- [Persistence and architecture](docs/explanation/architecture.md)

## Development

Part of the [axm-forge workspace](https://github.com/axm-protocols/axm-forge).
From the workspace root, install the workspace dependencies with `uv sync --all-groups`.
The package test directory is `packages/axm-config/tests_axm_config`.

Build this package's documentation from its directory with
`mkdocs build --strict`, using an environment containing its local installation,
MkDocs Material and mkdocstrings with the Python handler. The package configuration
also works when included by the workspace site.

## License

Apache-2.0 — © 2026 Gabriel Jarry
