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
