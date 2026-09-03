# How-To Guides

Task-oriented recipes for the real use cases of `axm-doctor`.

## Preflight an agent CLI's auth before a session

Before an orison / MCP session drives `gh`, `claude` or `codex`, check they are
logged in and surface the recovery command if not — value-free, no token read.

```python
from axm_doctor import detect_auth

for tool in ("gh", "claude", "codex"):
    status = detect_auth(tool)
    if status.state == "logged_out":
        print(f"{tool}: logged out — run: {status.login_cmd or 'n/a'}")
    elif status.state == "undetermined":
        print(f"{tool}: installed, but its session cannot be verified")
```

Use the combined preflight over MCP / the `axm` CLI via the
`auth_status` tool:

```bash
axm auth_status
# data = {
#   auth: {...},
#   undetermined: [...],
#   logged_out: [...],
#   credentials: {coordinate: {layer, present}},
# }
```

The `undetermined` and `logged_out` lists make the two non-connected-looking
outcomes explicit: only the latter proves that a session is closed. Alongside
the per-tool `auth` map, `credentials` reports the winning layer and presence
flag for every coordinate in the installed catalog. The rendered text lists
each coordinate followed by its layer; neither form contains a credential value.
An empty installed catalog yields an empty section.

## Bootstrap a new machine

On a fresh checkout, see what is missing, then repair interactively. `check` is
read-only; `bootstrap` gates every system change behind an explicit `y`.

```bash
axm-doctor check       # what is absent / logged out / missing?
axm-doctor bootstrap   # offer the official install for each absent tool,
                       # and vault setup for each missing secret
```

In a non-interactive shell (piped/closed stdin) `bootstrap` prompts for
nothing and installs nothing — it prints why and exits cleanly.

## Add a tool to the install registry

`install_command` only proposes commands it knows. To make a new tool
repairable, add its **official** install command to `_REGISTRY` in
`install.py` — an `InstallPlan` with a bare-exec `argv` (no shell), or a
`fetch_url` for a `curl | sh` script installer (downloaded then run as
`sh <tmpfile>`, never `shell=True`):

```python
"mytool": InstallPlan(
    tool="mytool",
    argv=["npm", "i", "-g", "@vendor/mytool"],
    human_command="npm i -g @vendor/mytool",
),
```

doctor still never guesses: an unknown tool returns `None`.

## Use `env_doctor` as a node in a loom graph

`env_doctor` is an `axm.tools` AXMTool, so it drops into a DAG via `tool_node`
without any adapter — a read-only env gate at the head of a graph:

```python
from axm import tool_node

env_gate = tool_node("env_doctor")   # fn(payload) -> {tools, auth, secrets, config}
```

Its `data` carries `tools`, `auth`, value-free `secrets`, and the
`config` block (`{git: {state}, gh: {state}}`) — everything the report exposes,
never a secret value.
