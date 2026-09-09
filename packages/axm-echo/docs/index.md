# axm-echo

Find similar documented Python symbols across packages, or search for a
helper matching an intention. Echo retrieves evidence for reuse and
deduplication; it does not prove semantic equivalence or change source files.

| Need | Entry point |
|---|---|
| Find cross-package duplicate candidates | `axm echo_code` |
| Search before implementing a helper | `axm echo_check --intention "..."` |
| Embed text or extract a Python corpus | `from axm_echo import embed, extract_package` |
| Compare normalized Python statement shapes | `statement_set` and `jaccard_similarity` |

## Start here

Install in a Python 3.12+ project with `uv add axm-echo`, then follow the
[getting-started tutorial](tutorials/getting-started.md). It uses a temporary
corpus and TF-IDF, so it needs no model download.

The tools default to the neural `st` backend; the Python `embed()` function
defaults to `tfidf`. Neural dependencies are part of the base install.
[Architecture and limits](explanation/architecture.md) explains the runtime
costs, model cache and limits of similarity scores.

## Find your way

- **Tutorial:** [extract and compare a controlled corpus](tutorials/getting-started.md).
- **How-to:** [configure scope](howto/configure-scope.md),
  [reuse during planning](howto/reuse-check-in-planning.md),
  [review clusters](howto/review-clusters.md),
  [compare structural shapes](howto/structural-similarity.md).
- **Reference:** [CLI and tools](reference/cli.md),
  [result contracts](reference/results.md), [Python API](reference/api/index.md).
- **Explanation:** [pipeline, tradeoffs and limits](explanation/architecture.md).

The corpus covers Python functions and classes exposed by their defining
modules. Both tools require docstrings; undocumented implementations are not
searched. Always check the resolved scope and the actual code before deciding
that an empty report permits a new implementation.
