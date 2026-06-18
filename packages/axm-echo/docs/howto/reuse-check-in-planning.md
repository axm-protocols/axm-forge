# Reuse check during planning with `echo_check`

When a plan is decomposed into tickets (the `/plan-tickets` workflow), every
ticket whose scope is *"develop a helper / function / class that does X"*
risks minting a duplicate of something the monorepo already provides — a
fifth retry helper, a third CSV reader, another `slugify`. `echo_check`
turns that risk into a deliberate decision.

This guide shows how to wire `echo_check` into the planning step that
gathers codebase intelligence, and how to act on its result.

## When to run it

Run the reuse check **only** for tickets that introduce *reusable
behaviour* — a new unit worth deduplicating. Skip it for pure glue, config
edits, dependency bumps, or scopes that are already "wire / refactor
existing code": there is no new helper to deduplicate there.

## 1. Retrieve the closest existing symbols

Call `echo_check` on the **intention** — a free-form description of the
behaviour the ticket would build:

```python
from axm_echo.tools import EchoCheckTool

result = EchoCheckTool().execute(
    intention="resilient HTTP call with retry on transient 5xx errors",
)
candidates = result.data["candidates"]
```

Via MCP / CLI the same call is `axm echo_check` or
`axm_call(name="echo_check", arguments={"intention": "..."})`.

Each candidate carries its `qualname`, `package`, `score`, full docstring
(`doc_full`), a location `verdict`, and a `promotable` flag:

| Field | Meaning |
|---|---|
| `verdict = "reuse_canonical"` | The hit lives in the canonical commons (`axm-ingot`) — reuse the canonical symbol directly. |
| `verdict = "reuse_in_place"` | A real helper exists in some package but has not been canonicalised — reuse it **in place** from `<package>`; do not mint a duplicate just because it is not in the ingot yet. |
| `promotable = True` | A well-documented non-ingot candidate worth canonicalising later. |

An **empty** candidate list means nothing scored above the retrieval
threshold — the intention is genuinely novel.

## 2. Decide reuse / extend / develop — read the docstrings, not the score

`echo_check` *retrieves and ranks*; it deliberately does **not** decide.
A `PARTIAL` match (similar docstring, different contract) can outrank a
perfect one, so never branch on the score or the verdict tag alone. Read
each candidate's `doc_full` and signature, compare its real contract
against the intention, and pick one branch:

| Decision | When | Ticket effect |
|---|---|---|
| **reuse** | A candidate already does *exactly* what the intention needs. | Rewrite the ticket to *"import / reuse `<qualname>` from `<package>` + wire it in"*; drop the implementation tasks, keep only wiring + tests. |
| **extend** | A candidate is the right *canonical* home but misses a parameter / mode / edge case. | Emit an **extension ticket** on `<qualname>` in `<package>`, and make the consumer ticket `blocks`-depend on it (extension lands first). |
| **develop** | No candidate covers the intention (empty list, or all near-misses with a different contract). | Write the "develop a helper" ticket as normal. |

## 3. Worked example

Spec line: *"the screener needs a resilient HTTP call (retry on 5xx)."*

```python
EchoCheckTool().execute(
    intention="resilient HTTP call with retry on transient errors",
)
```

If a candidate like `request_with_retry [axm-commons]` comes back with a
docstring matching the contract, **do not** emit "develop a retry helper".
Emit a **reuse** ticket — *"reuse `request_with_retry` from `axm-commons`
in the screener fetch path"* — with its implementation tasks dropped.

If nothing matches (empty candidate list), the helper genuinely does not
exist yet: emit the develop ticket.
