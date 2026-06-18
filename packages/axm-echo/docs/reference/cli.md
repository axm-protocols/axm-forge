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

## Python API

Auto-generated API reference is available under [Python API](api/).
