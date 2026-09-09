# axm-echo

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://pypi.org/project/axm-echo/)
[![Quality](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-echo/axm-audit.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml)
[![Coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-echo/coverage.json)](https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml)

Find similar documented Python symbols across packages and retrieve existing
helpers before implementing new ones. Results are candidates for review:
similar descriptions do not establish equivalent behaviour.

## Installation

Python 3.12+ is required. In a project environment:

```bash
uv add axm-echo
```

The base installation includes NumPy, scikit-learn, PyTorch and
sentence-transformers. Both AXM tools default to `st` (MiniLM); the Python
`embed()` function defaults to `tfidf`. Choosing TF-IDF avoids loading the
neural model at runtime, but does not remove the declared neural dependencies.
The first neural call may download model files and populate the model cache.

## Quick start

This example needs no repository or model download:

```python
from axm_echo import embed, neighbors

texts = [
    "retry an HTTP request after a transient error",
    "retry an HTTP request with exponential backoff",
    "parse a CSV document into rows",
]
matrix = embed(texts, backend="tfidf")
for index, score in neighbors(matrix[0], matrix[1:], k=2):
    print(f"{score:.3f}  {texts[index + 1]}")
```

For repository analysis, set a scope explicitly. From a workspace root:

```bash
AXM_ECHO_WORKSPACE_ROOTS="$PWD" axm echo_code --backend tfidf
AXM_ECHO_WORKSPACE_ROOTS="$PWD" axm echo_check \
  --intention "retry an HTTP request" --backend tfidf
```

`echo_code` groups cross-package candidates; `echo_check` ranks matches for
an intention. Both are registered as AXMTools, available through the generic
`axm` CLI and MCP. They read code, not rewrite it. An empty result is not
proof that no reusable implementation exists.

## Documentation

- [Getting started](docs/tutorials/getting-started.md): controlled corpus and retrieval.
- [Configure the scope](docs/howto/configure-scope.md): roots, fallback and discovery.
- [Review and acknowledge clusters](docs/howto/review-clusters.md).
- [CLI and tools](docs/reference/cli.md), [result contracts](docs/reference/results.md).
- [Python API](docs/reference/api/index.md) and [architecture](docs/explanation/architecture.md).
- [Published workspace documentation](https://forge.axm-protocols.io/).

The README is the repository entry point; [docs/index.md](docs/index.md) is
the MkDocs home page.

## Development

In the axm-forge checkout, start at the workspace root:

```bash
cd packages/axm-echo
uv run pytest
```

Running from the package directory selects its pytest configuration and
`tests_axm_echo` suite. The workspace's `make test-axm-echo` currently passes
`--package` to pytest rather than uv; use the package-directory command.

## License

MIT — © 2026 Gabriel Jarry
