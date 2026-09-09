# Python API

## Public imports

The package root exports the following names. The tables describe their
intended entry points; the sections below render their exact signatures.

| Group | Root exports |
|---|---|
| Corpus | `Symbol`, `SymbolDict`, `discover_package_roots`, `extract_package`, `extract_monorepo`, `load_scope` |
| Embedding | `Backend`, `code_tokens`, `embed`, `neighbors` |
| Structural comparison | `flatten_body`, `statement_set`, `normalize_dump`, `jaccard_similarity` |
| Tool | `EchoCodeTool` |

`EchoCheckTool` is registered as `echo_check` and importable from
`axm_echo.tools`, but is not re-exported by `axm_echo`. The other modules'
public helpers are implementation-level surfaces, not root exports.
The root does not export `__version__`.

## Corpus and scope contracts

`extract_package(Path(...))` returns a list of **dictionaries**, not
`Symbol` instances. `Symbol` is the dataclass used to construct those
records; `as_dict()` creates the dictionary view.

`SymbolDict` records carry `qualname`, `name`, `package`, `workspace`,
`kind`, `signature`, `doc_first_line`, `doc_full`, `body_norm`,
`embed_text`, `has_doc`, `path` and `line`. The extractor uses the
signature for `body_norm`; it does not capture bodies. Documented
`embed_text` combines signature and full docstring; undocumented text
combines the signature and its fallback.

Discovery uses [scope configuration](../../howto/configure-scope.md).
Functions/classes are selected according to axm-ast's module-public
convention, not membership in the package-root `__all__`. Module records
do not include every method as a separate corpus entry.

## Embedding contracts

`Backend` accepts `"tfidf"` or `"st"`. Library `embed()` defaults to
TF-IDF, unlike the tools. `code_tokens()` lowercases identifiers, splits
camelCase/snake_case and adds frequency-based control-flow hints.

Matrices are dense floating-point arrays with one row per input text.
Unknown backends raise `ValueError`; backend/library failures can propagate.
Use nonempty text inputs and guard an empty extracted corpus before indexing
`matrix[0]`. For TF-IDF, embed query and corpus together.

`neighbors()` normalizes internally, returns row indices and cosine scores
sorted descending, and retains scores equal to the threshold. It does not
remove the query row. `k <= 0` returns an empty list; dimensions must agree.
Zero vectors do not have a meaningful self-similarity of 1.0. See the
[worked tutorial](../../tutorials/getting-started.md).

## Structural contracts

See [structural comparison](../../howto/structural-similarity.md) for the
meaning and limits of the normalized statement sets.

## Root API

::: axm_echo
    options:
      members:
        - Backend
        - Symbol
        - SymbolDict
        - code_tokens
        - discover_package_roots
        - embed
        - extract_monorepo
        - extract_package
        - flatten_body
        - jaccard_similarity
        - load_scope
        - neighbors
        - normalize_dump
        - statement_set
      show_source: false

## Tools

Both registered tools and their exact execute signatures are included here.
Their payloads are specified in [result contracts](../results.md).

::: axm_echo.tools.EchoCodeTool
    options:
      members: [execute]
      show_source: false

::: axm_echo.tools.EchoCheckTool
    options:
      members: [execute]
      show_source: false
