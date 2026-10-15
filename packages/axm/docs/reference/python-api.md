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
| `DeclarativeToolDefinition`, `DeclarativeToolManifest`, `load_declarative_manifest` | Versioned UI tool metadata, JSON Schema validation and immutable declarations |
| `DeclarativeTool` | One shared adapter, explicitly unavailable without a host binding |
| `tool_access_scope`, `ToolAccessDenied` | Positive, context-local permissions including nested resolution and cached nodes |
| `tool_execution_guard` | Host-injected lease and argument-authority checks immediately before execution |
| `validate_declarative_schema` | Detached object schemas checked offline under the supported 2020-12 dialect |
| `tool_scope_sha256` | SHA256 of compact UTF-8 JSON containing sorted logical target names |
| `require_write_path` | Fail-closed write authority for a host-configured persisted target |
| `require_read_path` | Canonical read authority for explicit and configured persisted targets |

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

## Declarative UI tools

The frontend build publishes `ui/tools.json` in the installed resource package.
One entry point identifies that package, not an executable per tool:

```toml
[project.entry-points."axm.tool_manifests"]
rugby = "axm_rugby_orison"
```

The entry-point name must equal `addon_id`. The common resolver used by MCP,
CLI and `load_tool` reads this resource. It never compiles or scans Svelte.
Python tribunal/legacy precedence is unchanged; UI/Python collisions and duplicate
UI owners fail explicitly. A missing resource emits a provider-unavailable warning
without disabling legacy tools. Invalid or incompatible manifests fail closed.

```json
{
  "schema_version": 1,
  "addon_id": "rugby",
  "bundle_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "tools": [{
    "name": "rugby_ui_read_state",
    "handler": "rugby_ui_read_state",
    "description": "Read this view's presentation state",
    "inputSchema": {"type": "object", "additionalProperties": false},
    "outputSchema": {"type": "object"}
  }]
}
```

Schemas use JSON Schema 2020-12, object roots and local references only.
The same `validate_declarative_schema(schema) -> dict` helper validates view
snapshot schemas. It rejects remote references/IDs, non-2020-12 dialects and
custom vocabularies. Legacy `$recursiveRef`/`$recursiveAnchor` are refused rather
than silently ignored; use local `$dynamicRef` in the supported dialect.
Schema annotations/examples and property names remain data, not reference keywords.
Extra manifest fields are refused. Definitions detach their schema dictionaries;
mutating an input dictionary does not change the published contract. The host
separately verifies the bundle hash and owns target, revision, deduplication,
permissions and lifecycle. Metadata does not grant execution authority.

Without an explicit binding, a discovered `DeclarativeTool.execute` returns
`success=False`, status `unavailable`: no active-global-view fallback. A synchronous
host can inject `(name, arguments) -> ToolResult` into `DeclarativeTool`;
Orison's asynchronous host uses the scoped MCP factory. Successful `ToolResult.data`
must satisfy `outputSchema`; invalid arguments never reach the invoker.

CLI tools accept one JSON `--arguments` value, for example
`axm rugby_ui_read_state --arguments '{}'`; a headless call remains unavailable.
The generic transport is not a second implementation of persistent business actions.

`tool_access_scope(frozenset({...}))` filters discovery and denies name-based loads,
overrides and cached tool nodes outside the positive list. Nested scopes intersect
instead of widening; outside a scope, legacy behavior is unchanged. This is an
authorization contract for trusted tools, not a sandbox against arbitrary Python
code holding direct function references.

`tool_execution_guard(callback)` installs
`callback(name, detached_kwargs, original_execute) -> None`. A callback may normalize
the detached keyword arguments and raises on a stale lease or denied effect.
Scopes compose and restore using ContextVar; a nested scope cannot remove an outer
guard. Resolved handles preserve the implementation's signature and metadata while
retaining their creating guards. Tool-node caches retain only implementations,
then apply the current request's guards at every execution. Legacy resolution
without a scope/guard still returns the original implementation.
Retained handles also capture bound filesystem authority. During the service
body, the current caller and originating authority must both permit a read or
write; reusing a readonly handle inside a writable conversation cannot widen it.
The intersection remains active across nested dependency-read contexts. An
explicit None on either side denies authority and cannot borrow an ambient grant.

This cooperative boundary checks named dispatch immediately before invoking a
trusted tool. It cannot atomically revoke an effect already running or sandbox
arbitrary Python references. Business services still enforce their own validations.

::: axm.DeclarativeToolDefinition

::: axm.DeclarativeToolManifest

::: axm.load_declarative_manifest

::: axm.DeclarativeTool

::: axm.tool_access_scope

::: axm.tool_execution_guard

::: axm.validate_declarative_schema

::: axm.ToolAccessDenied

::: axm.tool_scope_sha256

`require_write_path(path)` is a separate service-side persistence guard. It raises
`PermissionError` without an active contract or outside its allowed write prefixes;
readable roots and dependency aliases do not grant writes. Relative paths resolve
against the contract execution root, never the ambient working directory, and
symlinks are canonicalized. Check the host-configured store/file before the canonical
mutation. Metadata tags alone do not classify arbitrary domain tools as writes.
MCP wrappers supply the bound contract; a local CLI can use an explicit
`AXM_WRITE_CONTRACT`. A trusted UI route retains its own host authorization and
shares the same business service rather than imitating an MCP click.

::: axm.require_write_path

`require_read_path(path)` must run after a business service resolves either a
caller-supplied store path or its configured default, immediately before opening
that target. A bound contract uses canonical `readable` authority (read roots and
declared dependency sources); relative paths use the execution root and symlinks
cannot escape. An explicitly transport-bound None refuses reads and suppresses
ambient contracts. Only legacy local callers with neither bound authority nor
ambient contract remain unrestricted. Read authorization grants no writes.

::: axm.require_read_path
