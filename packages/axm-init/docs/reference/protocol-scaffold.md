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

## Scaffold and preview surface

`init_scaffold` accepts protocol declarations through the same AXMTool
signature used by MCP and the generated CLI. Set `profile="protocols"` and a
`domain` when creating a standalone Python package or workspace member; the
tool records `[tool.axm-init.protocols]` in that package's
`pyproject.toml`. The structured result includes the derived distribution
name, package root, and creation mode.

For a unit preview, select `kind="protocol_unit"`; use `kind="protocol"`
when targeting an existing unit. In both cases, also provide `unit`, one or
more action-only payloads in `protocols`, and `preview=true`. The shared
`domain` and `unit` belong to the request and are injected into every
payload before validation as a strict `ProtocolScaffoldDecl`. The action then
completes each qualified graph name; `plan_protocol_scaffold` remains the
source of the relative operations.

The preview result has the same structured shape through direct AXMTool, MCP,
and CLI calls:

| Field | Meaning |
| --- | --- |
| `profile` | Selected profile (`protocols`) |
| `mode` | `unit` for preview; `standalone` or `member` for package creation |
| `root` | Absolute target package root |
| `preview` | `true` for a non-mutating plan |
| `created`, `updated`, `unchanged`, `conflicts` | Relative paths grouped by planner status |
| `protocols` | Qualified logical graph names |

Preview never applies planned file contents or merged metadata. Invalid
combinations are rejected before any write: protocol options without a profile,
a unit with an empty protocol list, the profile on a non-Python framework, or
protocol declarations without a unit.

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
