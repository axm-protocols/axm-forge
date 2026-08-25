# CLI Reference

## Commands

### `axm echo_code`

Detect cross-package code **echoes** — intent-equivalent duplicate symbols
across the configured monorepo. The tool walks the scope, embeds every public
documented symbol, finds cross-package pairs whose docstrings are semantically
close, applies the v7 anti-signals, and prints the surviving **clusters** plus
the demoted parallel-API / boilerplate buckets.

The command is auto-registered from the `axm.tools` entry point, so the same
implementation is reachable as an MCP tool and a DAG `tool_node` too.

```bash
# Cluster echoes across the corpus (~/.axm/config.toml [echo] scope, or the cwd).
axm echo_code

# The default backend is neural "st" (MiniLM, in-process). Opt into the
# pure-CPU tfidf backend to avoid loading torch.
axm echo_code --backend tfidf

# Raise the cosine floor for a candidate pair (default 0.55).
axm echo_code --threshold 0.7

# Show only the 10 nearest actionable clusters (the total stays in the header).
axm echo_code --top-n 10

# Tighten the over-merge guard (default 50): drop any component above 20.
axm echo_code --max-cluster-size 20
```

| Option | Default | Description |
| -- | -- | -- |
| `--backend` | `st` | Embedding backend: `st` (neural MiniLM, the in-process default) or `tfidf` (pure CPU, no torch). |
| `--threshold` | `0.55` | Minimum cosine similarity for a candidate pair. |
| `--top-n` | `30` | Bound the report to the N nearest *non-acknowledged* clusters. The neural pass still finds them all — only the display is bounded; the total count stays in the header. |
| `--max-cluster-size` | `50` | Reject any connected component larger than this as a union-find over-merge (a structural-conformity signal, not a duplicate echo — a genuine duplicate is 2-5 members). |

Output names the tool, the live/shown/actionable cluster counts, the corpus
size, and the demoted buckets, then lists each shown cluster's members with
their package and docstring first line:

```text
echo_code | 8 clusters, 3 shown (8 actionable) | corpus 16 symbols | 0 parallel-API · 0 boilerplate (demoted)

cluster 1  sim=1.000  (2 symbols)
  axm_commons.errors.RateLimitError  [axm-commons]  “Raised when the upstream API rate limit has been exceeded.”
  axm_bib.errors.RateLimitError  [axm-bib]  “Raised when the upstream API rate limit has been exceeded.”
```

#### Acknowledging a cluster (waiver)

A genuine cross-package echo that is *intended* (a parallel API, a deliberate
wrapper) is noise on every run. Acknowledge it in the **scan-root** `pyproject.toml`
(the first workspace root in `~/.axm/config.toml` `[echo]`) so it drops out of the
actionable top-N. Each entry is a 12-hex `cluster_hash` (printed in the tool's
`data.clusters[*].cluster_hash`) plus a non-empty `reason`:

```toml
[[tool.axm-echo.acknowledged]]
hash = "ca29d81fb73c"
reason = "parallel API, intended cross-package duplication"
```

An acknowledged *live* cluster is marked `acknowledged` and excluded from the
top-N and the `actionable_count`. The mechanism is self-cleaning: a waiver whose
hash no longer matches any live cluster is reported under
`data.stale_acknowledged` ("this waiver no longer serves a purpose, retire it")
— informative, never blocking. A malformed entry (bad hash, empty reason) is
rejected gracefully into `data.acknowledged_errors`; the run never crashes.

### `axm echo_check`

Retrieve the public symbols closest to a free-form **intention**, ranked by
semantic similarity across the whole monorepo. Before writing a new helper,
ask `echo_check` what already exists: it embeds the intention, returns the
top-k nearest documented symbols with their docstrings, and tags each with a
location **verdict** so you know whether to reuse the canonical symbol, reuse
one in place, or promote it.

The verdict is a *location* tag, not a decision: a high score means "this is
the closest existing promise", never "use this". The use / extend / nothing
call is left to the calling agent — a partial match may legitimately score
above an exact one.

Like `echo_code`, the command is auto-registered from the `axm.tools` entry
point, so the same implementation is reachable as an MCP tool and a DAG
`tool_node` too.

```bash
# Retrieve the closest existing symbols for an intention.
axm echo_check --intention "HTTP request with retry and backoff"

# The default backend is neural "st" (MiniLM, in-process). Opt into the
# pure-CPU tfidf backend to avoid loading torch.
axm echo_check --intention "slugify a string" --backend tfidf

# Raise the retrieval floor / cap the number of candidates.
axm echo_check --intention "parse a CSV file" --threshold 0.5 --k 3
```

| Option | Default | Description |
| -- | -- | -- |
| `--intention` | `""` | Free-form description of the behaviour to implement. |
| `--backend` | `st` | Embedding backend: `st` (neural MiniLM, the in-process default) or `tfidf` (pure CPU, no torch). |
| `--k` | `10` | Maximum number of candidates to return. |
| `--threshold` | `0.30` | Minimum cosine similarity for a candidate to be retrieved. Below it the candidate is dropped, so a novel intention returns an empty list rather than a spurious match. |

The verdict is set by the candidate's package: a hit in `axm-ingot` is
`reuse_canonical`; anything else is `reuse_in_place` (with a `promotable→ingot`
hint when the symbol is documented well enough to be worth canonicalising).

Output names the tool, the intention, the candidate count, and the corpus
size, then lists each ranked candidate with its package, similarity, verdict
and docstring first line:

```text
echo_check | “HTTP request with retry and backoff” | 1 candidates | corpus 2 symbols

1. axm_ingot.net.fetch_url  [axm-ingot]  sim=0.762  reuse_canonical
   "Perform an HTTP request, retrying with backoff on transient errors."
```

When nothing crosses the threshold the report says so explicitly, rather than
surfacing a weak false match:

```text
echo_check | “render a mermaid sequence diagram” | 0 candidates | corpus 2 symbols
(no candidate above threshold — likely novel)
```

## Python API

Auto-generated API reference is available under [Python API](api/).
