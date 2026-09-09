# CLI Reference

Echo declares `echo_code` and `echo_check` in the `axm.tools` entry-point
group. Install axm-echo in the same environment as the generic `axm` command
or MCP server. There is no separate `axm-echo` executable.

```bash
axm echo_code --help
axm echo_check --help
```

## Commands

### `axm echo_code`

Find cross-package duplicate **candidates** by embedding signatures and
docstrings, applying heuristics, then grouping surviving pairs.

```bash
AXM_ECHO_WORKSPACE_ROOTS="$PWD" axm echo_code --backend tfidf --top-n 10
axm echo_code --threshold 0.7 --max-cluster-size 20
axm echo_code --backend tfidf --json-output
```

| Option | Default | Contract |
|---|---|---|
| `--backend` | `st` | `st` (MiniLM) or `tfidf`. |
| `--threshold` | `0.55` | Inclusive cosine floor; must be in [0, 1]. |
| `--top-n` | `30` | Maximum displayed non-acknowledged clusters; integer ≥ 1. Does not reduce the scan. |
| `--max-cluster-size` | `50` | Components larger than this integer ≥ 1 are discarded, not split. |
| `--json-output` | false | Generic AXM option: print the tool's data dictionary. |

Clusters are sorted by their **highest edge score**, not their mean or
minimum similarity. Each demoted bucket contains at most 50 pairs in
`data`; separate counts retain the totals. The text report shows cluster
members and first-line docstrings, but omits hashes, waiver errors and full
demoted-pair details. Use JSON for [complete result contracts](results.md).

#### Acknowledging a cluster (waiver)

See [review and acknowledge clusters](../howto/review-clusters.md) for the
scan-root ownership rule, hash workflow and stale entries. Echo reads waivers;
it never writes or removes them.

### `axm echo_check`

Retrieve documented symbols matching a free-form intention.

```bash
AXM_ECHO_WORKSPACE_ROOTS="$PWD" axm echo_check \
  --intention "parse a CSV document into rows" --backend tfidf --k 3
axm echo_check --intention "retry an HTTP request" --json-output
```

| Option | Default | Contract |
|---|---|---|
| `--intention` | empty string | Must contain non-whitespace text. |
| `--backend` | `st` | `st` or `tfidf`. |
| `--k` | `10` | Maximum candidate count; integer ≥ 1. |
| `--threshold` | `0.30` | Inclusive cosine floor in [0, 1]. |
| `--json-output` | false | Print the data dictionary, including full candidate docstrings. |

An empty candidate list means no included symbol crossed the threshold. It
does not establish novelty. `reuse_canonical` depends only on the package
directory name `axm-ingot`. `promotable` checks docstring length, not purity,
dependency compatibility or API stability. See [planning](../howto/reuse-check-in-planning.md).

## MCP and Python

The same inputs use snake_case over MCP, for example `top_n` and
`max_cluster_size`. In an AXM façade client:

```text
axm_call(name="echo_check", arguments={
  "intention": "retry an HTTP request",
  "backend": "tfidf",
  "k": 3
})
```

The façade renders compact text. To consume full result data in Python:

```python
from axm_echo.tools import EchoCheckTool

result = EchoCheckTool().execute(
    intention="retry an HTTP request",
    backend="tfidf",
)
if not result.success:
    raise RuntimeError(result.error)
for candidate in result.data["candidates"]:
    print(candidate["qualname"], candidate["doc_full"])
```

This call uses the [configured scope](../howto/configure-scope.md).
`EchoCodeTool` is exported from `axm_echo`; `EchoCheckTool` is available
from `axm_echo.tools` and its registered tool name, not the package root.

Both tools return `ToolResult(success=False, error=...)` for supported input
validation failures or exceptions during execution. The generic CLI exits
nonzero on tool failure and writes errors to stderr. JSON mode prints only
`data`, so inspect the exit code as well as stdout. A successful result may
still be empty or contain
waiver errors: success is execution status, not a quality verdict. Python
callers must respect the annotated input types; not every wrong type is
converted into a ToolResult. Extra `**kwargs` are ignored by the tool
implementation, so misspelled Python/MCP options may silently do nothing.

## Python API

See [Python API](api/index.md) for library defaults and exports.
