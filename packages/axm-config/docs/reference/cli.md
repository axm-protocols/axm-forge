# CLI and AXMTools

## Console script

The distributed `axm-config` Cyclopts command wraps the central functions.
These are request/response commands, not daemon lifecycle commands.
Only the diagnostic tools below are registered as AXMTools.

| Invocation | Behavior |
|---|---|
| `axm-config get <namespace> <key>` | Prints the resolved value with Python `str`; absent values print `None`, exit 0. |
| `axm-config set <namespace> <key> <value>` | Persists a **string**; no TOML/JSON parsing and no success output. |
| `axm-config delete <namespace> <key>` | Removes the key; absent key is normally a no-op; pending legacy migration can still occur. |
| `axm-config path` | Creates/tightens and prints `~/.axm`, regardless of the selected profile. |
| `axm-config doctor [<namespace>]` | Prints `namespace.key: layer` lines for visible keys. |
| `axm-config --help` | Lists commands and usage. |

All store operations use `AXM_PROFILE`. Namespace/key validation failures,
`ConfigError` and caught filesystem errors print `error: ...` to stderr and
exit 1. Cyclopts handles argument parsing errors separately. There is no
`--config-path`, `--profile` or `--default` store option.

```bash
AXM_PROFILE=docs-cli axm-config set research.demo timeout 30
AXM_PROFILE=docs-cli axm-config get research.demo timeout
AXM_PROFILE=docs-cli axm-config doctor research.demo
AXM_PROFILE=docs-cli axm-config delete research.demo timeout
```

## config_doctor

```bash
axm config_doctor --namespace research.demo
```

MCP façade invocation: `axm_call(name="config_doctor", arguments={"namespace": "research.demo"})`.
The `namespace` argument is optional. The tool returns
`ToolResult(success=True, data=report, text=rendered_report)`; failures return
`success=False` and `error`.

Example data (values are deliberately absent):

```json
{"research.demo.timeout": {"layer": "env", "present": true}}
```

Keys are the union of the requested namespace's file keys and matching
environment keys. Without a namespace, only namespaces found in the selected
store or its legacy files are enumerated: an environment-only namespace is
omitted. No model schema is registered, so ordinary absent model defaults are
not enumerated. `default/present=false` is a possible provenance result,
not a catalogue of all built-in defaults.

The diagnostic parses the file internally. It does not return setting values
or modify configuration contents, but store access can create/chmod the AXM home.
It does not account for the typed accessors' additional `AXM_HOME` fallback.

Python tool class: `from axm_config.tools import ConfigDoctorTool`;
`execute(*, namespace=None)`. The root does not export this class.
The underlying `axm_config.doctor.config_doctor_data(namespace=None)` and
`render_doctor_report(report)` are internal module-level helpers.

## profile_isolation

```bash
AXM_HOME=/tmp/axm-profile-example axm profile_isolation --profile scratch
```

MCP façade: `axm_call(name="profile_isolation", arguments={"profile": "scratch"})`.
Python: root-exported `ProfileIsolationTool().execute(*, profile=None)`.
Omitting the profile uses `current_profile()`; invalid names produce a failed
ToolResult.

The data contains string paths under `tickets_db`, `warden_socket`,
`warden_log`, `sessions_root`, `quality_dir` and `protocols_dir`, plus
`profile` and boolean `isolated`. Text contains only the path lines.
Unlike the Python `ProfileIsolation` model, tool data omits `profile_root`
and `escapes`.

This is a side-effect-free calculation of candidate paths, not an audit of
actual configured consumers. Read the [profile limits](../howto/profiles.md).

The generic `axm` CLI discovers installed `axm.tools` entry points; command
availability depends on the environment. Neither `axm.commands` nor the
removed YAML hooks are required.

## Python API

See [public contracts](contracts.md) and the [rendered Python API](api.md).
