# Review and acknowledge clusters

Use acknowledgements for duplicate candidates that you have reviewed and
deliberately kept. They suppress repeated findings; they do not remove code
or certify equivalent behaviour.

## 1. Inspect the structured report

Set a known workspace scope, then include JSON so hashes are visible:

```bash
AXM_ECHO_WORKSPACE_ROOTS="$PWD" axm echo_code \
  --backend tfidf --top-n 30 --json-output
```

Read `clusters[*].members` in the CLI JSON (or `result.data["clusters"]`
in Python) at their source locations. A cluster is a
connected component and its score is the strongest edge: review all members,
not just the most similar pair. Counts and the bounded demoted buckets are
described in [result contracts](../reference/results.md).

## 2. Store a reason at the first scope root

Copy a real `cluster_hash` from the report into the `pyproject.toml` of
the **first root returned by `load_scope()`**. With multiple roots, echo
does not merge acknowledgements from all pyprojects.

Illustrative entry — replace the hash with the one from your report:

```toml
[[tool.axm-echo.acknowledged]]
hash = "ca29d81fb73c"
reason = "Reviewed: intentionally separate interfaces with different dependencies."
```

A valid entry needs a 12-character hex hash and a nonempty reason. The hash
uses members' `(package, qualname)` identities, independent of order.
Editing a function body without changing cluster membership does not change
this identity: revisit reasons when contracts change.

## 3. Re-run and maintain

The cluster remains in `cluster_count` but disappears from the returned
`clusters` and `actionable_count`. Read `stale_acknowledged` for unmatched
waivers and remove obsolete entries yourself. A different scope, threshold,
backend or component-size limit can make a waiver stale without any source
change.

Malformed entries are skipped into `acknowledged_errors` while execution
can still succeed. A missing, unreadable or invalid-TOML pyproject is treated
as no waivers; a corpus with fewer than two eligible symbols skips waiver
processing altogether. Echo never edits the pyproject automatically.
