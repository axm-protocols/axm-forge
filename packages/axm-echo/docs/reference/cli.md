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
# Cluster echoes across the corpus (~/.axm/echo.toml scope, or the cwd).
axm echo_code

# Pure-CPU backend (no torch); the default "st" needs the [neural] extra.
axm echo_code --backend tfidf

# Raise the cosine floor for a candidate pair (default 0.55).
axm echo_code --threshold 0.7
```

| Option | Default | Description |
| -- | -- | -- |
| `--backend` | `st` | Embedding backend: `st` (neural MiniLM, needs the `neural` extra) or `tfidf` (pure CPU). |
| `--threshold` | `0.55` | Minimum cosine similarity for a candidate pair. |

Output names the tool, the cluster count, the corpus size, and the demoted
buckets, then lists each cluster's members with their package and docstring
first line:

```text
echo_code | 1 clusters | corpus 2 symbols | 0 parallel-API · 0 boilerplate (demoted)

cluster 1  sim=1.000  (2 symbols)
  axm_commons.errors.RateLimitError  [axm-commons]  “Raised when the upstream API rate limit has been exceeded.”
  axm_bib.errors.RateLimitError  [axm-bib]  “Raised when the upstream API rate limit has been exceeded.”
```

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

# Pure-CPU backend (no torch); the default "st" needs the [neural] extra.
axm echo_check --intention "slugify a string" --backend tfidf

# Raise the retrieval floor / cap the number of candidates.
axm echo_check --intention "parse a CSV file" --threshold 0.5 --k 3
```

| Option | Default | Description |
| -- | -- | -- |
| `--intention` | `""` | Free-form description of the behaviour to implement. |
| `--backend` | `st` | Embedding backend: `st` (neural MiniLM, needs the `neural` extra) or `tfidf` (pure CPU). |
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
