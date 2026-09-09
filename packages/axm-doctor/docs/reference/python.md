# Python contracts

All names below are exported from `axm_doctor`. Results are frozen pydantic
models with `.model_dump()`; contained lists are not deeply immutable.

## Detection

| Call | Result / behavior |
| --- | --- |
| detect_tool(name) | ToolStatus(name, state, version=None, path=None); PATH then --version with 5-second timeout |
| detect_auth(tool) | AuthStatus(tool, state, login_cmd=None, declaration_consulted=False); declaration or PATH fallback |
| detect_git_identity() | GitIdentityStatus(state); truthy axm-config git.default, else git config --get user.email exit code |
| detect_gh_config() | GhConfigStatus(state); gh config get git_protocol exit code |

`ToolState` is present/absent. `AuthState` is logged_in/logged_out/not_installed/
undetermined. `GitIdentityState` is configured/unconfigured; `GhConfigState`
additionally allows not_installed. An unparseable version remains None without
changing present to absent.

Declared connected maps to logged_in; tool_absent to not_installed; all other
outcomes, failures and guard timeouts map to logged_out. Without a declaration,
PATH presence yields undetermined and absence not_installed. The detector
currently leaves login_cmd=None. Discovery is repeated per call.

Git/gh subprocess errors become unconfigured. The axm-config import/get occurs
outside that handler and can raise. A truthy git.default does not validate a
complete committer identity. Non-sensitive config values are retrieved, and
command stdout is captured then discarded; none is returned.

## Provenance

`collect_credential_provenance(*, probe=None)` returns a list of
`CredentialProvenance(coordinate: str, kind: str="credential", layer: str,
present: bool)`. A supplied probe bypasses live catalog discovery:

```python
from axm_doctor import collect_credential_provenance

def example_provenance():
    return {
        "example.service.api_key": {
            "kind": "token", "layer": "missing", "present": False
        }
    }

rows = collect_credential_provenance(probe=example_provenance)
assert rows[0].kind == "token"
assert rows[0].present is False
```

This example contains synthetic metadata only. Malformed entries degrade to
unknown/absent; failure to obtain the whole catalog/report can still raise.
The missing layer forces present=False.

## Installation

`install_command(tool) -> InstallPlan | None` supports uv, claude, codex;
unknown tools return None. The built-in uv URL is currently pinned to
`https://astral.sh/uv/0.8.4/install.sh`; npm plans install
`@anthropic-ai/claude-code` and `@openai/codex`.

InstallPlan fields: tool (str), argv (list[str]), human_command (str),
fetch_url (str | None, default None).
`run_install(plan, *, confirm=False)` returns InstallResult fields:
command (str), executed (bool), returncode (int | None, default None),
post_check (ToolStatus | None, default None).

Dry-run executes and probes nothing. Confirmed execution runs the command then
re-detects the tool. Success requires returncode=0 and a present post_check.
Executed=True alone is not installation success.

Execution uses shell=False. Script downloads require an initial HTTPS URL,
status 200 and at most 1 MiB, with a 30-second download timeout. The temporary
script runs via sh and is removed afterward. The process has no timeout.
Missing executables and rejected/download-failed scripts return 127.
Filesystem failures outside those handlers can raise.
Custom plans are accepted: there is no registry allowlist or checksum/signature
verification. Validate application-supplied plans before confirmation.

## Missing credentials and provisioning

`missing_secrets()` returns list[MissingSecret], excludes auth_dependency
and includes missing optional specs. It matches canonical credential/account
coordinates exactly, so a served account cannot mask a missing sibling.

| MissingSecret field | Type / default |
| --- | --- |
| group, name, package, setup_hint | str, required |
| required | bool, required |
| instance | str or None, default None |
| awaiting_instance | bool, default False |

A multi group with no declared accounts yields awaiting_instance.
The setup_hint omits the account: `axm-vault set <group> <name>`.

`provision_missing(*, confirm=False)` plans distinct groups; confirmation
requires a TTY and delegates to vault run_setup(only=group) per group.

| ProvisionResult field | Type / default |
| --- | --- |
| provisioned | bool, required |
| groups | list[str], required |
| still_missing | list[str], default [] |
| reason | str or None, default None |

Dry-run leaves still_missing empty. After confirmed setup the entire current
catalog is rescanned; True requires nonempty groups and no remaining missing
specs. An empty catalog does not produce True. Non-TTY and caught SystemExit
return early with a reason and without re-scan. Other errors can propagate.
Earlier groups may already have changed; no rollback exists. still_missing
uses group.name strings and omits account identity.

## Tools

EnvDoctorTool and AuthStatusTool expose zero-argument execute() methods.
See [the data and error contract](cli.md#mcp-and-generic-axm-cli) and
[generated signatures](api.md).
