# axm-doctor

Environment detection, install planning and credential setup orchestration for
AXM. Python 3.12+; part of the [axm-forge workspace](https://github.com/axm-protocols/axm-forge).

## Install and inspect

```bash
uv add axm-doctor
uv run axm-doctor check
uv run axm-doctor check --strict
```

`check` reports tools, third-party authentication, declaration provenance and
missing credentials. It does not install or prompt. Normal reporting exits 0;
`--strict` exits 1 for absent tools, `logged_out` auth or any missing credential,
including optional ones. Operational errors also exit 1 without `--strict`.

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

## Choose an interface

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

## Boundaries

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

The README is the repository entry point; [docs/index.md](docs/index.md) is the
site homepage. Build this package independently from its directory with
`mkdocs build --strict` after installing the documentation dependencies
(MkDocs Material and mkdocstrings with its Python handler).

## License

Apache-2.0 — © 2026 Gabriel Jarry
