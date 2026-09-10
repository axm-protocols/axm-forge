# Protocol registration and declared state

Request these checks with `init_check(..., category="protocols")`. They inspect
local files without importing the inspected package or loading installed
registries. A passing scaffold check alone does not establish executability.

## Rules

| Canonical name | Failure conditions | Diagnostic |
| --- | --- | --- |
| `protocols.protocol_registration` | A draft has a graph entry; a ready protocol lacks an entry under its graph name resolving to its public `build_protocol` factory; a declared target resolves elsewhere or cannot be resolved; inspected identities collide within one registry | Metadata or source location, offending target or identity, and correction; collisions list the conflicting declarations |
| `protocols.protocol_draft` | A ready action contains `# axm-init: incomplete-skeleton` in an inspected Python module | Source file, marker line, and correction |

Both functions in `axm_init.checks.protocols` accept `project: Path` and return
`CheckResult`: `check_protocol_registration` and `check_protocol_draft`.
Registration has weight 2 when the inventory contains declared protocols.
The draft rule has weight 2 when at least one declaration is ready; an inventory
containing only drafts produces a passing, zero-weight draft result. Without an
applicable inventory, both rules return passing, zero-weight results.

Graph entries come from `[project.entry-points."axm.graphs"]` in
`pyproject.toml`. Resolution follows local imports, including relative imports,
and simple identifier aliases, with cycle detection. An absent module, absent
symbol or binding to a different function cannot establish factory registration.
Dynamic bindings are not executed to discover their value.

Collision detection considers declarations actually inspected in the selected
package and, at a workspace root, its profiled members. Graph identities come
from a literal protocol composition argument when resolvable, otherwise a
literal `GRAPH_NAME` in `protocol.py`. Ticket identities come from literal
`TICKET_TYPE` declarations in `ticket.py`. The `axm.graphs` and `axm.ticket_types`
identity spaces are separate; a ticket's `GRAPH_NAME` reference is not another
graph declaration. This is not an inventory of installed distributions or a
validation of installed ticket entry points.

Workspace aggregation retains each canonical rule name and member attribution.
Cross-member collisions are added by the central category inventory.

## Structured tool result

For an explicit `protocols` category request, `InitCheckTool` adds a `protocols`
list to `ToolResult.data`, including when checks fail. This list is available in
agent and JSON output modes as well as the ordinary tool result.

| Entry field | Meaning |
| --- | --- |
| `member` | Member identity, or the standalone directory name |
| `graph_name` | Identity derived from the declared domain, unit and action |
| `state` | Declared state, normally `draft` or `ready`; omission defaults to `draft` in this inventory |
| `location` | Metadata state location, with line 1 as a fallback |
| `validated` | True only for a ready declaration when all evaluated protocol-category checks pass and no protocol check was explicitly excluded |
| `executable` | Currently uses the same static predicate as `validated`; it is not an execution probe |

Validation is conservative across the result: a category failure, including a
failure in another member, keeps these flags false. A ready declaration with a
missing registration still has `state="ready"`, with both flags false. A draft
always has both flags false, even when its scaffold is conforming. Consumers
should use this inventory instead of inferring readiness from `passed_count`,
summary text or passing-check details. The shared `CheckResult` and
`ProjectResult` models have no additional state field.

See [how to check readiness](../howto/scaffold-protocols.md#check-registration-and-readiness)
and [protocol declarations](protocol-scaffold.md).
