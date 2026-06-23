# axm-doctor

Env bootstrap + auth-status doctor (detect, propose, orchestrate)

<p align="center">
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-systems/axm-draft-workspace/gh-pages/badges/axm-doctor/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-systems/axm-draft-workspace/gh-pages/badges/axm-doctor/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-systems/axm-draft-workspace/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-systems/axm-draft-workspace/gh-pages/badges/axm-doctor/coverage.json" alt="Coverage"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
</p>

---

## Overview

Env bootstrap + auth-status doctor (detect, propose, orchestrate)

## Features

- ✅ **Pure-stdlib detection** — `detect_tool` / `detect_auth` answer "is `uv` installed?" / "is `gh` logged in?" with **zero AXM dependencies** (stdlib + pydantic only), so they run as the bootstrap layer before any AXM package is importable.
- ✅ **Read-only auth** — auth state is inferred from an exit code (`gh auth status`) or the **presence of a non-empty** credential file (`~/.claude/.credentials.json`, `~/.codex/auth.json`); the file is stat'd, not opened, so the token value is never read (a 0-byte file is reported `logged_out`, not `logged_in`).
- ✅ **Frozen result models** — `ToolStatus` and `AuthStatus` are immutable pydantic models; `AuthStatus` carries the recovery `login_cmd` but never a token.
- ✅ **Install plans, never silent installs** — `install_command` proposes the *official* install command for a known tool (`uv`, `claude`, `codex`) without running anything; `run_install` is a **dry-run by default** (`confirm=False`) that only echoes the command it would run. It installs strictly when the caller opts in with `confirm=True`, then re-detects the tool via `detect_tool`.
- ✅ **Orchestrates, never possesses** — `missing_secrets` reads the **axm-vault** catalog and value-free resolver provenance to list the credential specs that resolve to `missing` (carrying `group / name / package / setup_hint`, never a value). `provision_missing` is a **dry-run by default** (`confirm=False`) that returns the groups it *would* prompt for; on `confirm=True` it delegates to vault's `run_setup(only=…)`. The secret value never transits axm-doctor — every write goes through vault's API.

```python
from axm_doctor import detect_tool, detect_auth

detect_tool("uv")      # ToolStatus(name='uv', state='present', version='0.5.1', path=...)
detect_auth("gh")      # AuthStatus(tool='gh', state='logged_in', login_cmd=None)
detect_auth("claude")  # AuthStatus(tool='claude', state='logged_out', login_cmd='claude login')
```

```python
from axm_doctor import install_command, run_install

plan = install_command("uv")          # InstallPlan(tool='uv', human_command='curl -LsSf https://astral.sh/uv/install.sh | sh', ...)
install_command("bogus")              # None — never guesses a command

run_install(plan)                     # dry-run (confirm=False): executed=False, nothing installed, command echoed
run_install(plan, confirm=True)       # installs, then re-detects: InstallResult(executed=True, returncode=0, post_check=ToolStatus(...))
```

```python
from axm_doctor import missing_secrets, provision_missing

missing_secrets()                     # [MissingSecret(group='research.fred', name='api_key', package='axm-research', setup_hint='axm-vault set research.fred.api_key'), ...]
                                      # [] when the vault catalog is empty — never reads a secret value

provision_missing()                   # dry-run (confirm=False): ProvisionResult(provisioned=False, groups=['research.fred']) — the groups it WOULD prompt for
provision_missing(confirm=True)       # delegates to vault's run_setup(only=...); doctor never stores a secret itself
                                      # in a non-interactive shell (no TTY) it provisions nothing: ProvisionResult(provisioned=False, reason=...)
```

## CLI

The `axm-doctor` console script has two commands:

```bash
axm-doctor check       # read-only env report (tools + auth + missing secrets); never installs or prompts
axm-doctor bootstrap   # interactive repair: installs absent tools / runs vault setup only on an explicit "y"
```

The same read-only surface is exposed as the `env_doctor` and `auth_status`
`axm.tools` (MCP + `axm <tool>` CLI + DAG node); `auth_status` never serializes
a token value.

## Installation

```bash
uv add axm-doctor
```

Or as a workspace dependency in `pyproject.toml`:

```toml
[project]
dependencies = ["axm-doctor"]

[tool.uv.sources]
axm-doctor = { workspace = true }
```

## Development

This package is part of the **axm-draft-workspace** uv workspace.

```bash
# Run tests for this package
uv run pytest --package axm-doctor

# From workspace root
make test-axm-doctor
```

## License

Apache-2.0 — © 2026 Gabriel Jarry
