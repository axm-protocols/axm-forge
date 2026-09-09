# Getting started

Install doctor, read a report and inspect a repair plan without applying it.

## Install

Use Python 3.12+ in a project:

```bash
uv add axm-doctor
uv run axm-doctor --help
uv run axm-doctor check
```

Alternatively, install with `pip install axm-doctor` in an active virtual
environment, then run `axm-doctor check`.

## Read the report

The following is an abbreviated illustrative report, not expected output for
your machine. Installed declarations determine the credential rows.

```text
tool	uv	present	0.8.4
tool	codex	absent	-
auth	codex	✗	not_installed	-
auth	gh	?	undetermined	-
token	example.service.api_key	missing
secret	example.service.api_key	axm-vault set example.service api_key
```

An absent binary needs installation. An `undetermined` session has no installed
declaration capable of checking it. A declared probe producing `logged_out`
may have failed or timed out; investigate it before treating it as a known
logout. The current detector does not populate recovery `login_cmd`.

Normal reporting returns exit 0, including this unhealthy example.
`axm-doctor check --strict` returns 1 for absent tools, `logged_out` auth
or missing credentials. Runtime errors also return 1 in either mode.

## Query a tool

```python
from axm_doctor import detect_tool

status = detect_tool("uv")
print(status.state, status.version)
```

Presence is based on PATH. A binary whose version cannot be parsed remains
`present`, with `version=None`; this does not verify compatibility.

## Propose a repair

```python
from axm_doctor import install_command, run_install

plan = install_command("uv")
assert plan is not None
print(plan.human_command)
result = run_install(plan)
assert result.executed is False
assert result.returncode is None
assert result.post_check is None
assert install_command("unknown-example-tool") is None
```

This is a dry-run: no download, install, or post-install probe occurs.
The registry's uv plan pins 0.8.4. Inspect the plan before deciding to run it.

## Continue

Use [bootstrap](../howto/bootstrap.md) when you are ready to make changes.
For automation, use the [preflight guide](../howto/preflight.md);
consult [Python contracts](../reference/python.md) for results and errors.
