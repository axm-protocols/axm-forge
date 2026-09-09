# Result contracts

The structured envelope is the AXM `ToolResult`: inspect `success` before
reading `data`. Error text is diagnostic, not a stable error code.
CLI `--json-output` prints the **data dictionary only**: fields listed below
are at the JSON root, with no `success` envelope. Check the exit code and
stderr for failure. The MCP façade's compact text does not include every field.

## echo_code

| Field in `data` | Meaning |
|---|---|
| `corpus_size` | Documented symbols remaining after accessor filtering. |
| `clusters` | At most `top_n` non-acknowledged clusters, strongest edge first. |
| `cluster_count` | All surviving clusters, including acknowledged ones; oversized components already excluded. |
| `actionable_count` | Surviving non-acknowledged count, before display truncation. |
| `shown_count` | Length of `clusters`. |
| `parallel_api`, `boilerplate` | Each at most 50 strongest demoted pairs. |
| `parallel_api_count`, `boilerplate_count` | Full bucket counts before truncation. |
| `stale_acknowledged` | Valid waiver entries whose hash matches no current surviving cluster. |
| `acknowledged_errors` | Schema diagnostics for invalid waiver entries/section. |

A shown cluster contains `size`, `score` (maximum pair score rounded to four
decimals), `members` and `cluster_hash`. A member contains `qualname`,
`name`, `package`, `doc_first_line`, `path` and `line`.
A demoted pair contains `score`, `a` and `b`, with the same member fields.

Waived clusters are marked internally then excluded from `data.clusters`;
do not expect returned `acknowledged=True` records. Clusters are connected
components: members need not all match one another above the threshold.

When fewer than two documented non-accessor symbols remain, the tool returns
a successful empty payload. This early return skips reading waivers, so stale
waivers and schema errors are not diagnosed in that case. An unreadable or
invalid-TOML waiver file also degrades to no waivers without a diagnostic.

## echo_check

| Field in `data` | Meaning |
|---|---|
| `intention` | The supplied search text. |
| `corpus_size` | Documented corpus size; accessors are retained. |
| `candidates` | Up to `k` threshold-qualified hits, descending cosine. |

Each candidate contains:

| Field | Contract |
|---|---|
| `qualname`, `name`, `package` | Symbol identity; package is the scanned directory's name. |
| `path`, `line` | Source location. |
| `doc_first_line`, `doc_full` | First line and complete docstring. |
| `score` | Cosine rounded to four decimals after selection. |
| `verdict` | `reuse_canonical` for `axm-ingot`, otherwise `reuse_in_place`. |
| `promotable` | True for a non-ingot hit with at least 40 stripped docstring characters. |

The candidate payload does **not** include a signature or function body.
Read the source or inspect the symbol with axm-ast before deciding to reuse
it. The compact text includes only the docstring's first line.

An empty corpus returns success with no candidates and does not load an
embedding backend. Nonempty corpora can still yield zero candidates because
of vocabulary, wording or the threshold. Neither `verdict` nor `promotable`
checks exports from a package root, dependency direction or side effects.

## Failure and cost boundaries

Invalid backend names, out-of-range thresholds, nonpositive report limits
and blank intentions fail. Embedding or corpus errors caught during a tool
run produce failure; some parser/read failures are instead skipped during
extraction. The library functions may raise exceptions directly.

`top_n` and `k` bound output, not corpus extraction or embedding. Pair
generation is exhaustive across different package names; a low threshold can
produce many pairs even when the final output is small.
