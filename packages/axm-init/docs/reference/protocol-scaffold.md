# Protocol declarations

The declaration models in `axm_init.models.protocol_scaffold` describe the
components needed to scaffold a protocol. They validate names and references
before any files are generated.

## Protocol model

`ProtocolScaffoldDecl` requires the three graph-name segments, contracts, and
nodes. Its `graph_name` property joins `domain`, `unit`, and `action`
with dots. This name is independent from an optional ticket type.

Prompts, phases, and the complete ticket block may be omitted. Omitted
collections default to empty lists.

| Component | Required fields | Optional fields |
| --- | --- | --- |
| `ContractDecl` | `name` | — |
| `PromptDecl` | `name`, `text` | — |
| `NodeDecl` | `name` | `contract`, `prompt` |
| `PhaseDecl` | `name` | `nodes` (defaults to an empty list) |
| `TicketDecl` | `ticket_type`, `input_contract` | — |

A ticket block is optional as a whole. When present, its
`input_contract` remains required.

## Reference validation

Every supplied reference must resolve inside the same declaration:

- a node contract names a declared contract;
- a node prompt names a declared prompt;
- each phase node names a declared node;
- a ticket input contract names a declared contract.

Validation errors include the unresolved reference. Component names must also
be unique within each list, and generated model or factory names must not
collide.

All name segments must be safe lowercase Python identifiers. Path separators,
parent traversal, absolute paths, reserved words, and extra fields are rejected.

## Scaffold, preview and application surface

`init_scaffold` accepts protocol declarations through the same AXMTool
signature used by MCP and the generated CLI. Set `profile="protocols"` and a
`domain` when creating a standalone Python package or workspace member; the
tool records `[tool.axm-init.protocols]` in that package's
`pyproject.toml`. The structured result includes the derived distribution
name, package root, and creation mode.

Select `kind="protocol_unit"` for a new unit or `kind="protocol"` when
targeting an existing unit. In both cases, also provide `unit` and one or more
action-only payloads in `protocols`. Set `preview=true` to inspect the plan
without mutation; leave it false to apply that exact plan. The shared `domain`
and `unit` belong to the request and are injected into every payload before
validation as a strict `ProtocolScaffoldDecl`. The action then completes each
qualified graph name; `plan_protocol_scaffold` is the sole source of the
relative operations and rendered contents.

The preview result has the same structured shape through direct AXMTool, MCP,
and CLI calls:

| Field | Meaning |
| --- | --- |
| `profile` | Selected profile (`protocols`) |
| `mode` | `unit` for protocol planning or application; `standalone` or `member` for package creation |
| `root` | Absolute target package root |
| `preview` | `true` for a non-mutating plan; `false` after application |
| `created`, `updated`, `unchanged`, `conflicts` | Relative paths grouped by planner status |
| `protocols` | Qualified logical graph names |

Preview never applies planned file contents or merged metadata. Application
creates or updates only paths carried by the plan and writes the merged
`[tool.axm-init.protocols]` metadata; it does not invoke a standalone-project
template. Reapplying an owned plan leaves unchanged files byte-for-byte, including
skeletons extended by a compatible implementation.

Before the first mutation, application resolves every destination and rejects
paths outside the root, outward-pointing symlinks, conflicts, and incompatible
occupied paths. If a file or metadata write fails after application begins, it
removes paths created by that operation and restores the original file and
metadata bytes. This is application-level rollback, not crash-safe atomicity.

Invalid request combinations are also rejected before any write: protocol
options without a profile, an empty protocol list when `unit` or `preview` is set, the profile on a
non-Python framework, or protocol declarations without a unit.

## Example

```python
from axm_init.models.protocol_scaffold import ProtocolScaffoldDecl

declaration = ProtocolScaffoldDecl(
    domain="dev",
    unit="work",
    action="exec",
    contracts=[
        {"name": "work_request"},
        {"name": "work_result"},
    ],
    prompts=[
        {"name": "implement", "text": "Implement the requested change."},
    ],
    nodes=[
        {"name": "prepare"},
        {
            "name": "implement",
            "contract": "work_result",
            "prompt": "implement",
        },
    ],
    phases=[
        {"name": "build", "nodes": ["prepare", "implement"]},
    ],
    ticket={
        "ticket_type": "engineering.change",
        "input_contract": "work_request",
    },
)

assert declaration.graph_name == "dev.work.exec"
```

## Current interface notes

Declaration requests require an existing package with a readable `pyproject.toml`.
The orchestrator processes actions sequentially against a virtual inventory,
so later actions see earlier planned content.

`ScaffoldResult` also carries `success`, `path`, `message`, `files_created`
and optional `distribution`. The human message currently remains
`Protocol scaffold preview` even on application; `preview` is the authoritative
mode flag. A preview can report conflicts without applying them.

Rollback is in-process; it does not serialize concurrent writers or supply a
durable recovery journal. See [the operational guide](../howto/scaffold-protocols.md).
