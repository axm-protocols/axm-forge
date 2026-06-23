# CLI Reference

The `axm-doctor` console script exposes two commands. The split is deliberate:
`check` is **read-only** (it never installs and never prompts), while
`bootstrap` is the **interactive** path where any system change is gated behind
an explicit `y`.

## `axm-doctor check`

Print the full environment report and exit `0`. For every probed tool it prints
presence + version; for every third-party binary it prints the auth state and
the recovery `login_cmd`; for every missing secret it prints the `group.name`
and the `axm-vault` setup hint.

```console
$ axm-doctor check
tool	uv	present	uv 0.9.18
tool	gh	present	gh version 2.87.3
tool	codex	absent	-
auth	gh	logged_in	-
auth	claude	logged_out	claude login
secret	research.fred.api_key	axm-vault set research.fred.api_key
```

`check` **installs nothing and prompts for nothing** — it is safe to run in CI
or a hook.

## `axm-doctor bootstrap`

The interactive repair path. For each **absent** tool it shows the official
install command and installs it only on an explicit `y` (default *No*); for
missing secrets it offers to run vault setup. Nothing happens without a yes —
this honours the no-system-install-without-authorization posture.

```console
$ axm-doctor bootstrap
codex is absent. Install command: npm i -g @openai/codex
install codex? [y/N] n
  skipped: npm i -g @openai/codex
```

The install outcome is reported from the **post-check**, not merely from the
fact that the command ran: a confirmed install is only `installed (<tool> now
present)` when it returns `0` *and* the tool is re-detected as present;
otherwise it is `install failed (rc=<n>, still absent)`. A declined prompt is
`skipped: <command>`.

```console
$ axm-doctor bootstrap
codex is absent. Install command: npm i -g @openai/codex
install codex? [y/N] y
  install failed (rc=1, still absent)
```

In a **non-interactive** shell (no TTY, e.g. a closed or piped stdin) `bootstrap`
cannot prompt, so both halves skip cleanly rather than crashing on the first
prompt. The tool-install loop prints `non-interactive shell: skipping tool
installs` and installs nothing; secret provisioning is likewise skipped —
`provision_missing` returns `provisioned=False` with a `reason` rather than
letting vault's setup driver abort the process.

```console
$ axm-doctor bootstrap < /dev/null
non-interactive shell: skipping tool installs
```

Under the hood `bootstrap` delegates to the central functions — `run_install`
for tools and `provision_missing` for secrets — so the confirm gate is the only
logic the CLI adds.

## MCP tools

The same read-only surface is available as two `axm.tools` entry points (MCP +
`axm <tool>` CLI + DAG node):

| Tool | Returns |
| -- | -- |
| `env_doctor` | `{tools, auth, secrets}` — tool presence/version, third-party auth state, and value-free missing secrets. Read-only. |
| `auth_status` | `{auth: {tool: {state, login_cmd}}}` for the third-party binaries. The token value is **never** serialized. |

## Python API

Auto-generated API reference is available under [Python API](api/).
