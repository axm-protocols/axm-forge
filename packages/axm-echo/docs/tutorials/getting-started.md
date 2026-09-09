# Getting Started

Build a small Python corpus, retrieve similar descriptions, then run the
same search through the CLI. The tutorial uses TF-IDF so it does not load
PyTorch or download model weights.

## Prerequisites

Use Python 3.12+ and install the package in a project environment:

```bash
uv add axm-echo
```

The installation includes the neural dependencies even though this tutorial
uses TF-IDF. The tools default to `st`; `embed()` defaults to `tfidf`.

## Step 1: Embed a Few Texts

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

Rows correspond to input texts. We leave the first row out of the search
matrix to avoid returning the query itself. Returned indices refer to
`matrix[1:]`, hence the `+ 1` when looking up the original text.
Scores depend on the corpus and backend; they are not confidence probabilities.

## Step 2: Extract a Corpus From Code

Run this complete script in the installed environment. It creates and removes
its own temporary files, and never consults your configured workspace scope.

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from axm_echo import embed, extract_package, neighbors

with TemporaryDirectory(prefix="echo-tutorial-") as directory:
    package = Path(directory) / "sample"
    source = package / "src" / "sample"
    source.mkdir(parents=True)
    (source / "helpers.py").write_text(
        'def retry_request():\n'
        '    """Retry an HTTP request after a transient error."""\n'
        '    return None\n\n'
        'def parse_rows():\n'
        '    """Parse a CSV document into rows."""\n'
        '    return []\n',
        encoding="utf-8",
    )
    symbols = extract_package(package)
    assert len(symbols) == 2
    intention = "retry an HTTP request"
    matrix = embed([intention, *[s["embed_text"] for s in symbols]])
    hits = neighbors(matrix[0], matrix[1:], k=2, threshold=0.1)
    for index, score in hits:
        print(symbols[index]["qualname"], round(score, 3))
    assert symbols[hits[0][0]]["name"] == "retry_request"
```

These functions are deliberately small fixtures, not implementations to
reuse. Extraction returns dictionaries with signatures, docstrings and source
locations. Function bodies are not extracted: the `body_norm` fallback holds
the signature. Extraction can include undocumented symbols, while the tools
filter them out.

## Step 3: Search Your Workspace

From a workspace you want to scan:

```bash
AXM_ECHO_WORKSPACE_ROOTS="$PWD" axm echo_check \
  --intention "retry an HTTP request" --backend tfidf --k 3
AXM_ECHO_WORKSPACE_ROOTS="$PWD" axm echo_code --backend tfidf --top-n 10
```

The assignment scopes these commands without editing configuration. Review
`corpus_size` and the candidate source before taking action. A zero result
can reflect missing docstrings, the selected roots or filtering.

## Next Steps

- [Configure the scope](../howto/configure-scope.md).
- [Make a reuse decision](../howto/reuse-check-in-planning.md).
- [Review and acknowledge clusters](../howto/review-clusters.md).
- [Read exact output fields](../reference/results.md).
