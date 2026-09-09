# CLI reference

The package distributes `axm-doctor = axm_doctor.cli:main` and two
`axm.tools` entry points. No legacy YAML hooks or `axm.commands` are needed.

## Check

```bash
axm-doctor check
axm-doctor check --strict
```

The current tool set is `uv`, `git`, `gh`, `node`, `npm`, `claude`,
`codex`; the auth set is `gh`, `claude`, `codex`.
The CLI prints tab-separated rows in this order:

| Row | Columns after row type |
| --- | --- |
| `tool` | name, present/absent, parsed version or `-` |
| `auth` | tool, marker, state, login command or `-` |
| Declared kind (e.g. `token`, `auth_dependency`) | decoded coordinate, layer/state |
| `secret` | group.name, setup hint |

Auth markers are ✓ for `logged_in`, ? for `undetermined`, and ✗ otherwise.
`login_cmd` is currently always absent in detector results.
Config states are only in `env_doctor`, not this CLI report.
Credential rows depend on installed providers; an empty catalog is valid.
The CLI decodes provenance coordinates for display and omits account identity
from `secret` labels. Prefer structured results for machine consumption.

| Outcome | Exit code |
| --- | --- |
| Normal report without strict | 0, even with missing components |
| Strict: absent tool, logged_out auth, or any missing credential | 1 |
| Strict: none of those conditions | 0 |
| Exception caught while building a report | 1; error on stderr |

Strict mode derives its verdict from the same scan. Optional missing secrets
also fail it; `required` is not used. `undetermined` auth does not fail it.
Provenance rows and git/gh config states are not additional strict checks.

## Bootstrap

```bash
axm-doctor bootstrap
```

Interactive confirmation delegates installs to `run_install` and credential
setup to `provision_missing`. See [the bootstrap guide](../howto/bootstrap.md)
for TTY behavior, mutation boundaries and partial failures.

A declined install prints `skipped: <command>`. A confirmed install prints
success only for return code 0 plus a present post-check; otherwise it reports
failure. Reported install/provision failures do not themselves set exit 1;
caught exceptions do. No automatic authentication login or config repair exists.

## MCP and generic AXM CLI

```bash
axm env_doctor
axm auth_status
```

`EnvDoctorTool.execute()` and `AuthStatusTool.execute()` take no arguments
and return `ToolResult`. The generic CLI also exposes `--json-output`
(and `--no-json-output`); use its help to inspect transport options. The following
describes `data`, not the default rendered CLI text. MCP façades may expose
rendered text only.

| Tool | Data fields |
| --- | --- |
| `env_doctor` | `tools`: name → {state, version}; `auth`: tool → {state, login_cmd, declaration_consulted}; `secrets`: complete MissingSecret rows; `config`: {git: {state}, gh: {state}} |
| `auth_status` | `auth`: same map; `undetermined` and `logged_out`: tool-name lists; `credentials`: coordinate → {layer, present} |

Illustrative auth entry (JSON fragment):

```json
{"state": "undetermined", "login_cmd": null, "declaration_consulted": false}
```

`auth_status` text groups provenance by kind and appends `[no declaration]`
for tools lacking one. `kind` is present in `CredentialProvenance`, but is
not a field of its public `credentials` map.

Successful report construction yields `success=True` even for unhealthy
observations. `auth_status` wraps collection exceptions into
`ToolResult(success=False, error=...)`. `env_doctor` wraps its tool/secret
collection, but currently builds auth/config outside that try block; a config
lookup exception can propagate from direct Python execution. See
[limits](../explanation/architecture.md#current-limits).

## Python

[Contracts and models](python.md) · [Generated API](api.md)
