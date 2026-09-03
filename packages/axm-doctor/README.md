# axm-doctor

Env bootstrap + auth-status doctor (detect, propose, orchestrate)

<p align="center">
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge-workspace/gh-pages/badges/axm-doctor/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge-workspace/gh-pages/badges/axm-doctor/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge-workspace/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge-workspace/gh-pages/badges/axm-doctor/coverage.json" alt="Coverage"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
</p>

---

## Overview

Env bootstrap + auth-status doctor (detect, propose, orchestrate)

## Features

- ✅ **Bootstrap-safe detection** — importing `axm_doctor` (or `axm_doctor.detect`) pulls **no** AXM package: `detect.py` defers its AXM imports and the package re-exports lazily (PEP 562). `detect_tool` remains a stdlib + pydantic probe. On each `detect_auth` call, the credential catalog is discovered lazily; if it is unavailable, detection safely degrades to binary presence.
- ✅ **Config-resolvability checks** — `detect_git_identity` reports whether a git committer identity is resolvable (a truthy `[git].default` in the **axm-config** store, else the exit code of `git config --get user.email`) and `detect_gh_config` reports whether `gh` carries a base config (`gh config get git_protocol` exit code; `not_installed` when `gh` is absent). Value-free like auth: only the store presence and exit codes are inspected, never the identity/config value. Both degrade to `unconfigured` on any error instead of raising. The `env_doctor` tool surfaces them under a `config` key (`{git: {state}, gh: {state}}`).
- ✅ **Declaration-driven, read-only auth** — each package that drives a third-party tool declares how to probe it and owns every tool-specific path, service name and recovery command. `detect_auth` only translates the declaration outcomes into `logged_in`, `logged_out` or `not_installed`; it never reads or returns authentication material. Without a declaration, an installed binary yields `undetermined` because its session cannot be verified, while an absent binary yields `not_installed`.
- ✅ **Frozen result models** — `ToolStatus`, `AuthStatus`, `GitIdentityStatus` and `GhConfigStatus` are immutable pydantic models; authentication results contain state metadata, never a token.
- ✅ **Install plans, never silent installs** — `install_command` proposes the *official* install command for a known tool (`uv`, `claude`, `codex`) without running anything; `run_install` is a **dry-run by default** (`confirm=False`) that only echoes the command it would run. It installs strictly when the caller opts in with `confirm=True`, then re-detects the tool via `detect_tool`.
- ✅ **Kind-aware, value-free provenance** — `collect_credential_provenance` reports each declaration with its coordinate, declared `kind`, serving layer/state, and presence flag. Credential kinds (for example `token`) and `auth_dependency` coexist in one report; a failing declaration is isolated as `unknown` / absent without erasing healthy peer verdicts.
- ✅ **Orchestrates, never possesses** — `missing_secrets` reads the **axm-vault** catalog and value-free resolver provenance to list credential specs that resolve to `missing`; `auth_dependency` declarations are excluded because an OAuth/session dependency is not a secret to provision. A `MissingSecret` can identify the account concerned with `instance` or signal that a multi-instance group declares no account yet with `awaiting_instance`; account lookups use only axm-vault's exact canonical coordinate, so a served sibling cannot hide a starving account. `provision_missing` is a **dry-run by default** (`confirm=False`) that returns only credential groups it *would* prompt for; on `confirm=True` it delegates to vault's `run_setup(only=…)`. The secret value never transits axm-doctor — every write goes through vault's API.

```python
from axm_doctor import detect_tool, detect_auth
from axm_doctor.detect import detect_git_identity, detect_gh_config

detect_tool("uv")      # ToolStatus(name='uv', state='present', version='0.5.1', path=...)
detect_auth("gh")      # declaration outcome -> AuthStatus(state='logged_in', ...)
detect_auth("unknown") # no declaration: PATH presence -> undetermined / not_installed
detect_git_identity()  # GitIdentityStatus(state='configured')  — store [git].default or `git config user.email`
detect_gh_config()     # GhConfigStatus(state='configured')     — `gh config get git_protocol`
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

missing_secrets()                     # MissingSecret rows; instance identifies the account when known
                                      # awaiting_instance=True means a multi group declares no account yet
                                      # [] when the vault catalog is empty — never reads a secret value

provision_missing()                   # dry-run (confirm=False): ProvisionResult(provisioned=False, groups=['research.fred']) — the groups it WOULD prompt for
provision_missing(confirm=True)       # delegates to vault's run_setup(only=...); doctor never stores a secret itself
                                      # in a non-interactive shell (no TTY) it provisions nothing: ProvisionResult(provisioned=False, reason=...)
```

## CLI

The `axm-doctor` console script has two commands:

```bash
axm-doctor check       # read-only report (tools + auth + provenance by kind + missing credentials)
axm-doctor bootstrap   # interactive repair: installs absent tools / runs vault setup only on an explicit "y"
```

The same read-only surface is exposed as the `env_doctor` and `auth_status`
`axm.tools` (MCP + `axm <tool>` CLI + DAG node). `auth_status` keeps its
value-free `{layer, present}` data contract while its text groups provenance by
declared kind; it never serializes a token value.

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

This package is part of the **axm-forge** uv workspace.

```bash
# Run this package's tests (from the workspace root)
uv run --package axm-doctor pytest packages/axm-doctor

# Lint + type-check + tests for the whole workspace
make check
```

## License

Apache-2.0 — © 2026 Gabriel Jarry
