---
hide:
  - navigation
  - toc
---

# axm-doctor

<p align="center">
  <strong>Env bootstrap + auth-status doctor (detect, propose, orchestrate)</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge-workspace/actions/workflows/ci.yml">
    <img src="https://github.com/axm-protocols/axm-forge-workspace/actions/workflows/ci.yml/badge.svg" alt="CI" />
  </a>
  <a href="https://github.com/axm-protocols/axm-forge-workspace/actions/workflows/axm-quality.yml">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge-workspace/gh-pages/badges/axm-doctor/axm-init.json" alt="axm-init" />
  </a>
  <a href="https://github.com/axm-protocols/axm-forge-workspace/actions/workflows/axm-quality.yml">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge-workspace/gh-pages/badges/axm-doctor/axm-audit.json" alt="axm-audit" />
  </a>
  <a href="https://github.com/axm-protocols/axm-forge-workspace/actions/workflows/axm-quality.yml">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge-workspace/gh-pages/badges/axm-doctor/coverage.json" alt="Coverage" />
  </a>
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+" />
</p>

---

## Installation

```bash
uv add axm-doctor
```

## Quick Start

```python
from axm_doctor import detect_tool, detect_auth

# Is a tool on PATH? (stdlib + pydantic only, no AXM dependency imported)
print(detect_tool("uv"))      # ToolStatus(state='present', version='0.5.1', ...)

# Resolve a package-owned, read-only authentication declaration.
print(detect_auth("gh"))       # declaration_consulted=True + declared outcome
print(detect_auth("unknown"))  # declaration_consulted=False + PATH fallback
```

```python
from axm_doctor import install_command, run_install

# Propose the official install command — runs nothing.
plan = install_command("uv")     # InstallPlan(human_command='curl -LsSf https://astral.sh/uv/install.sh | sh', ...)

# Dry-run by default — NEVER installs silently.
run_install(plan)                # InstallResult(executed=False, ...): echoes the command it would run
run_install(plan, confirm=True)  # opt-in install, then re-detects via detect_tool
```

```python
from axm_doctor import (
    collect_credential_provenance,
    missing_secrets,
    provision_missing,
)

# Which kind and layer/state describe each installed declaration? Returns no values.
collect_credential_provenance()  # [CredentialProvenance(coordinate=..., kind=..., layer=..., present=...)]

# Which credential specs resolve to 'missing'? Auth dependencies are excluded.
missing_secrets()                # MissingSecret rows; instance identifies the account when known
                                 # awaiting_instance=True means a multi group declares no account yet

# Dry-run by default — NEVER prompts or stores.
provision_missing()              # ProvisionResult(provisioned=False, groups=['research.fred']): the groups it WOULD prompt for
provision_missing(confirm=True)  # delegates to vault's run_setup(only=...) — doctor never writes a secret itself
```

## Features

- ✅ **Bootstrap layer** — importing the detection surface pulls no AXM package (deferred AXM imports + PEP 562 lazy re-exports). `detect_tool` uses stdlib + pydantic only; `detect_auth` discovers the credential catalog lazily and safely falls back to binary presence when the catalog is unavailable.
- ✅ **Config-resolvability checks** — `detect_git_identity` (a `[git].default` in the **axm-config** store, else `git config --get user.email` exit code) and `detect_gh_config` (`gh config get git_protocol` exit code; `not_installed` when `gh` is absent) report whether a git committer identity and `gh` base config are resolvable — value-free (presence + exit code only, never the value), degrading to `unconfigured` on error. The `env_doctor` tool surfaces them under a `config` key.
- ✅ **Declaration-driven, read-only auth** — packages that drive third-party tools own their probes and all tool-specific session knowledge. `detect_auth` only maps declaration outcomes to `logged_in`, `logged_out` or `not_installed`; no authentication material transits through doctor. `AuthStatus.declaration_consulted` is `True` whenever an installed declaration was found and consulted, even if its probe could not conclude. Without a declaration it is `False`: PATH presence yields `undetermined`, while an absent binary remains `not_installed`.
- ✅ **Frozen models** — immutable `ToolStatus` / `AuthStatus` / `GitIdentityStatus` / `GhConfigStatus`; authentication results expose state metadata, never a token.
- ✅ **Install plans, never silent installs** — `install_command` proposes the official command for a known tool; `run_install` is a dry-run by default (`confirm=False`) and installs only on explicit opt-in (`confirm=True`), then re-detects the tool.
- ✅ **Typed declaration provenance** — `collect_credential_provenance` translates axm-vault's live, value-free report into immutable `CredentialProvenance` rows containing a coordinate, declared `kind`, serving layer/state, and presence flag. Credential kinds and `auth_dependency` rows coexist; one raising declaration degrades only its own row to a cautious `unknown` / absent verdict. `auth_status` preserves its per-tool `auth` map and value-free `{layer, present}` credential shape, while exposing separate `undetermined` and `logged_out` tool lists so consumers do not mistake an unverifiable session for a closed one.
- ✅ **Orchestrates, never possesses** — `missing_secrets` lists credential specs that resolve to `missing` (value-free, with a `setup_hint`) and excludes `auth_dependency` entries, which cannot be provisioned as secrets. `MissingSecret.instance` identifies the account concerned and `awaiting_instance` marks a multi-instance group with no declared account; the served-state lookup uses the exact canonical credential/account coordinate, never a sibling match. `provision_missing` is a dry-run by default and on `confirm=True` delegates only credential groups to vault's `run_setup` — the secret never transits axm-doctor.

---

<div style="text-align: center; margin: 2rem 0;">
  <a href="tutorials/getting-started/" class="md-button md-button--primary">Get Started →</a>
  <a href="reference/cli/" class="md-button">Reference</a>
</div>
