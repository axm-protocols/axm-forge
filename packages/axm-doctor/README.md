<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>axm-doctor — Environment detection and setup orchestration</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-doctor/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-doctor/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-doctor/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-doctor/"><img src="https://img.shields.io/pypi/v/axm-doctor" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://forge.axm-protocols.io/axm-doctor/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

Environment detection, install planning and credential setup orchestration for
AXM. Python 3.12+; part of the [axm-forge workspace](https://github.com/axm-protocols/axm-forge).

## Features

- Report installed tools, authentication states and missing credentials.
- Prepare install plans without executing them.
- Expose structured preflight through AXM tools and a human-readable CLI.
- Orchestrate confirmed setup through axm-vault without owning a secret store.

## Installation

Requires Python 3.12 or newer. In a Python project managed by uv:

```bash
uv add axm-doctor
```

## Quick Start

After installation, inspect the environment:

```bash
uv run axm-doctor check
```

`check` reports tools, third-party authentication, declaration provenance and
missing credentials. It does not install or prompt. Normal reporting exits 0;
`--strict` exits 1 for absent tools, `logged_out` auth or any missing credential,
including optional ones. Operational errors also exit 1 without `--strict`.

## Usage

### Choose an interface

| Need | Interface |
| --- | --- |
| Human-readable environment report / CI exit code | `axm-doctor check [--strict]` |
| Structured request–response preflight | `env_doctor` AXMTool |
| Authentication and value-free provenance | `auth_status` AXMTool |
| Inspect one tool or prepare an install | Root Python exports |
| Interactive install / vault setup | `axm-doctor bootstrap` |

The AXM tools are discovered through `axm.tools`, exposed as `axm env_doctor`
and `axm auth_status`, through MCP, and through `tool_node`. Successful
report generation does not mean the machine is healthy; evaluate the returned
states for your own preflight policy.

### Install and inspect

Use `uv run axm-doctor check --strict` when the report should gate CI.

```python
from axm_doctor import install_command, run_install

plan = install_command("uv")
assert plan is not None
print(plan.human_command)
result = run_install(plan)
assert not result.executed
```

Planning runs nothing. Installation requires `run_install(plan, confirm=True)`.
The built-in uv plan currently pins 0.8.4; a plan is not a latest-version lookup.

### Boundaries

- Importing `axm_doctor` resolves exports lazily; `detect_tool` needs only
  stdlib and pydantic. Full reports also use axm-config and axm-vault.
- Authentication probes belong to installed credential declarations. Without
  a declaration, an installed binary is `undetermined`. A declared probe
  failure or timeout is currently `logged_out`; it is not proof of logout.
  `detect_auth` currently leaves `login_cmd=None`.
- Reports contain metadata, not credential values. Detection can launch
  subprocesses and invoke provider probes; read-only does not mean no I/O.
- Doctor owns no credential store. `provision_missing()` plans groups;
  confirmed execution delegates writes and prompts to vault.

## Documentation

[Getting started](docs/tutorials/getting-started.md) ·
[Task guides](docs/howto/index.md) ·
[CLI](docs/reference/cli.md) ·
[Python contracts](docs/reference/python.md) ·
[Architecture and limits](docs/explanation/architecture.md)

[Published documentation](https://forge.axm-protocols.io/axm-doctor/).

The README is the repository entry point; [docs/index.md](docs/index.md) is the
site homepage.

## Development

From the axm-forge workspace root:

```bash
uv sync --all-packages --all-groups
uv run --package axm-doctor --directory packages/axm-doctor pytest
uv run --package axm-doctor --directory packages/axm-doctor --group docs mkdocs build --strict
```

The package's configured test root is `tests_axm_doctor/`. Its standalone
MkDocs build uses the documentation dependencies from the `docs` group.

## License

Licensed under Apache-2.0. See [LICENSE](LICENSE).
