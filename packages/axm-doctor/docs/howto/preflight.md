# Preflight an agent or DAG

Use the request–response tools for a structured observation:

```bash
axm env_doctor
axm auth_status
```

Both tools accept no arguments. They are discovered from the installed
`axm.tools` entry points, so the interpreter hosting AXM/MCP must have
axm-doctor installed. See [the exact data contract](../reference/cli.md#mcp-and-generic-axm-cli).

## Interpret authentication conservatively

```python
from axm_doctor import detect_auth

status = detect_auth("codex")
if status.state == "logged_in":
    print("Declaration reports connected")
elif status.state == "not_installed":
    print("Install the required binary")
elif status.state == "undetermined":
    print("No declaration: verify the session separately")
else:
    print("Declaration reports disconnected or failed; investigate the probe")
```

`declaration_consulted` records whether a declaration was found, not whether
its probe succeeded. `login_cmd` currently remains `None`.
Doctor neither logs in nor refreshes sessions.

## Map DAG outputs explicitly

```python
from axm import tool_node

env_probe = tool_node(
    "env_doctor",
    returns={
        "observed_tools": "tools",
        "observed_auth": "auth",
        "missing_credentials": "secrets",
        "observed_config": "config",
    },
)
# Within the graph, invoke env_probe({}) and evaluate its returned observations.
```

Building this callable does not probe the environment. `returns` determines
the emitted keys: omitting it produces an empty mapping, not the tool's full
data. The caller must turn observations into a policy or gate. Missing
credentials retain `required`, `instance` and `awaiting_instance`, allowing a
policy more selective than the CLI's strict mode.

## CI report gate

```bash
axm-doctor check --strict
```

This fixed policy includes all probed binaries and all missing credentials,
even optional specs. It ignores `undetermined` auth, git/gh configuration and
the standalone provenance rows. It is not a general guarantee of readiness.
