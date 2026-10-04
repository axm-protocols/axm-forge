# Python SDK reference

## Stable root imports

`from axm import ...` supports the following contracts:

| Export | Purpose |
|---|---|
| `AXMTool` | Structural tool protocol: `name` and `execute` |
| `ToolResult` | Tool success, data, error, hint and text |
| `ToolMetadata`, `tool_metadata` | Optional discovery settings and their defaults |
| `tool_node`, `ToolNodeError` | Tool-to-node adapter and its contract errors |
| `WitnessRule`, `WitnessResult`, `ValidationFeedback` | Validation contracts |
| `__version__` | Installed distribution version; `"0.0.0"` if metadata is missing |

Definitions remain in their submodules. Prefer root imports for these
contracts. `load_tool` and `override_tools` are additionally re-exported by
`axm.tools`. CLI helpers and `axm.tools.write_scope` are implementation
modules, not root SDK exports.

## Tool results

`ToolResult` is a frozen dataclass, not a Pydantic model. It requires
`success`; `data` defaults to a fresh empty dict, and `error`, `hint`,
`text` default to `None`. Frozen fields do not make nested data immutable.

`data` is for machine consumers; `text` is an optional prepared rendering.
Neither automatically derives from the other. `hint` is available to
consumers but the generic CLI does not print it as a separate field.
Use `dataclasses.asdict` when you explicitly need the whole dataclass;
the CLI's shared `--json-output` emits only `data`.

::: axm.tools.base.ToolResult
    options:
      skip_local_inventory: true

::: axm.tools.base.AXMTool
    options:
      skip_local_inventory: true

## Discovery metadata

`tool_metadata(tool)` returns `ToolMetadata` with defaults
`expose_directly=False`, `domain=None`, `tags=frozenset()`.
It uses attributes rather than requiring inheritance. Tags are coerced to a
frozenset; `expose_directly` is converted with `bool`.

`agent_hint` is a separate optional attribute, absent from `ToolMetadata`.
The helper does not invent an agent hint or guarantee a docstring fallback.

::: axm.tools.base.ToolMetadata
    options:
      skip_local_inventory: true

::: axm.tools.base.tool_metadata
    options:
      skip_local_inventory: true

## Tool nodes

Read the [composition guide](../howto/tool-node.md) before choosing mappings
and failure handling. `ToolNodeError` is a `RuntimeError` subclass.

::: axm.tools.node.tool_node
    options:
      skip_local_inventory: true

::: axm.tools.node.ToolNodeError
    options:
      skip_local_inventory: true

::: axm.tools.node.load_tool
    options:
      skip_local_inventory: true

::: axm.tools.node.override_tools
    options:
      skip_local_inventory: true

## Process sandbox

`axm.sandbox` runs a subprocess that may write only under given directories,
in a filtered environment. It is a submodule contract, not a root export.

| Symbol | Purpose |
|---|---|
| `confinement(writable, protected=())` | Probe the platform sandbox (`sandbox-exec` on macOS, `bwrap` on Linux) with the profile it will apply; `Confinement(isolation="sandbox")` or `UNCONFINED` (`"detect-only"`) |
| `run_confined(command, *, writable, cwd, env=None, protected=(), timeout=None, confined=None)` | Run one command under a confinement; returns `ConfinedRun` (isolation, return code, output) |
| `inherited_environment(source=None)` | The allow-listed variables (`INHERITED_ENV`) only: no `PYTHONPATH`, `FORCE_COLOR` or credentials |
| `private_environment(root)` | `HOME`, temporary and XDG variables pointed into fresh directories of `root` |
| `darwin_profile`, `bubblewrap_argv` | The platform prefixes, for callers that launch the process themselves |

A `detect-only` confinement does not confine anything: callers refuse it or
report it, never treat it as a sandbox. A protected path inside a writable
directory stays read-only. On macOS, `sandbox-exec` applies explicit write
denials for protected paths after the writable allowances. On Linux,
`bubblewrap` mounts the filesystem read-only, binds writable directories, then
remounts every protected path read-only after those writable binds. Both
platforms enforce the protection when `confinement` reports `sandbox`.

::: axm.sandbox.run_confined
    options:
      skip_local_inventory: true

::: axm.sandbox.confinement
    options:
      skip_local_inventory: true

## Other contracts

[Witnesses](witnesses.md) covers the remaining root protocols
and result types. [CLI reference](cli.md#python-api) documents launcher helpers.

The workspace build also generates module reference pages from
`docs/gen_ref_pages.py`. This curated reference renders directly from the same
source, so it works in both package-only and monorepo builds.

## Declared instrument runtime

`axm.DependencyEnvironment` is the immutable runtime transported with a phase
contract. `axm.session_dependency_environment(project_path)` returns the matching
declared environment, or None only without a contract. A missing or ambiguous
runtime, an unrelated readable root, or a missing interpreter fails explicitly.
The interpreter retains its lexical virtualenv path. Resolving this runtime does
not grant additional filesystem write authority.
