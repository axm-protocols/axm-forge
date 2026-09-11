<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>axm-echo — Similarity detection and reuse retrieval for Python code</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-echo/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-echo/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-echo/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-echo/"><img src="https://img.shields.io/pypi/v/axm-echo" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://forge.axm-protocols.io/axm-echo/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

Find similar documented Python symbols across packages and retrieve existing
helpers before implementing new ones. Results are candidates for review:
similar descriptions do not establish equivalent behaviour.

## Features

- Group similar documented symbols across packages with `echo_code`.
- Retrieve existing helpers matching an intention with `echo_check`.
- Choose MiniLM neural embeddings or TF-IDF similarity.
- Use Python embedding and nearest-neighbor functions on your own text corpus.
- Configure repository scope and review acknowledged clusters without rewriting code.

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

## Quick Start

After installation, run this in the project's Python environment. It needs no
repository or model download:

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

The output ranks the two remaining descriptions by cosine similarity to the
first; the retry description appears before the CSV description.

## Usage

### Repository tools

For repository analysis, set a scope explicitly. From a workspace root in
the environment where axm-echo is installed:

```bash
AXM_ECHO_WORKSPACE_ROOTS="$PWD" uv run axm echo_code --backend tfidf
AXM_ECHO_WORKSPACE_ROOTS="$PWD" uv run axm echo_check \
  --intention "retry an HTTP request" --backend tfidf
```

`echo_code` groups cross-package candidates; `echo_check` ranks matches for
an intention. Both are registered as AXMTools, available through the generic
`axm` CLI and MCP. They read code, not rewrite it. An empty result is not
proof that no reusable implementation exists.

### Python API

The quick-start functions `embed` and `neighbors` are available from
`axm_echo`. Embed a TF-IDF query and its corpus together so their dimensions
and vocabulary agree. For repository extraction, scope and structural
comparison, see the [Python API](docs/reference/api/index.md).

## Documentation

- [Getting started](docs/tutorials/getting-started.md): controlled corpus and retrieval.
- [Configure the scope](docs/howto/configure-scope.md): roots, fallback and discovery.
- [Review and acknowledge clusters](docs/howto/review-clusters.md).
- [CLI and tools](docs/reference/cli.md), [result contracts](docs/reference/results.md).
- [Python API](docs/reference/api/index.md) and [architecture](docs/explanation/architecture.md).
- [Published package documentation](https://forge.axm-protocols.io/axm-echo/).

The README is the repository entry point; [docs/index.md](docs/index.md) is
the MkDocs home page.

## Development

In the axm-forge checkout, start at the workspace root:

```bash
uv sync --all-packages --all-groups
uv run --package axm-echo --directory packages/axm-echo pytest
```

Running from the package directory selects its pytest configuration and
`tests_axm_echo` suite. The workspace's `make test-axm-echo` currently passes
`--package` to pytest rather than uv; use the package-directory command.

## License

Licensed under Apache-2.0. See [LICENSE](LICENSE).
