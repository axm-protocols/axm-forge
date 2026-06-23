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
  <a href="https://github.com/axm-systems/axm-draft-workspace/actions/workflows/ci.yml">
    <img src="https://github.com/axm-systems/axm-draft-workspace/actions/workflows/ci.yml/badge.svg" alt="CI" />
  </a>
  <a href="https://github.com/axm-systems/axm-draft-workspace/actions/workflows/axm-quality.yml">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-systems/axm-draft-workspace/gh-pages/badges/axm-doctor/axm-init.json" alt="axm-init" />
  </a>
  <a href="https://github.com/axm-systems/axm-draft-workspace/actions/workflows/axm-quality.yml">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-systems/axm-draft-workspace/gh-pages/badges/axm-doctor/axm-audit.json" alt="axm-audit" />
  </a>
  <a href="https://github.com/axm-systems/axm-draft-workspace/actions/workflows/axm-quality.yml">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-systems/axm-draft-workspace/gh-pages/badges/axm-doctor/coverage.json" alt="Coverage" />
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

# Is a tool on PATH? (pure stdlib, no AXM dependency)
print(detect_tool("uv"))      # ToolStatus(state='present', version='uv 0.5.1', ...)

# Is a third-party CLI logged in? (read-only: exit code / credential-file existence)
print(detect_auth("gh"))      # AuthStatus(state='logged_in', login_cmd=None)
print(detect_auth("claude"))  # AuthStatus(state='logged_out', login_cmd='claude login')
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
from axm_doctor import missing_secrets, provision_missing

# Which credential specs resolve to 'missing'? Reads vault's catalog + value-free provenance.
missing_secrets()                # [MissingSecret(group='research.fred', name='api_key', setup_hint='axm-vault set research.fred.api_key'), ...] — never a value

# Dry-run by default — NEVER prompts or stores.
provision_missing()              # ProvisionResult(provisioned=False, groups=['research.fred']): the groups it WOULD prompt for
provision_missing(confirm=True)  # delegates to vault's run_setup(only=...) — doctor never writes a secret itself
```

## Features

- ✅ **Bootstrap layer** — `detect_tool` / `detect_auth` depend on stdlib + pydantic only, never on `axm-config` / `axm-vault`, so they run before any AXM package is installed.
- ✅ **Read-only auth** — state comes from an exit code or a non-empty credential-file check (a 0-byte file is `logged_out`); on macOS, `claude` is probed via the login Keychain entry `Claude Code-credentials` (exit code only). The file is stat'd, not opened, and the Keychain value is never read, so the token value is never read.
- ✅ **Frozen models** — immutable `ToolStatus` / `AuthStatus`; `AuthStatus` carries a `login_cmd` to recover from `logged_out`, never a token.
- ✅ **Install plans, never silent installs** — `install_command` proposes the official command for a known tool; `run_install` is a dry-run by default (`confirm=False`) and installs only on explicit opt-in (`confirm=True`), then re-detects the tool.
- ✅ **Orchestrates, never possesses** — `missing_secrets` lists the vault credential specs that resolve to `missing` (value-free, with a `setup_hint`); `provision_missing` is a dry-run by default and on `confirm=True` delegates to vault's `run_setup` — the secret never transits axm-doctor.

---

<div style="text-align: center; margin: 2rem 0;">
  <a href="tutorials/getting-started/" class="md-button md-button--primary">Get Started →</a>
  <a href="reference/cli/" class="md-button">Reference</a>
</div>
