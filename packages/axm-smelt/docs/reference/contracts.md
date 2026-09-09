# Python and tool contracts

## Public imports

Import the supported Python surface from `axm_smelt`:

| Export | Contract |
|---|---|
| `smelt` | Produce compacted text and a `SmeltReport` |
| `check` | Measure individual strategies and the default pipeline |
| `count` | Count a string with a selected tiktoken encoding/model |
| `SmeltReport` | Pydantic report described below |
| `Format` | Enum: `JSON`, `YAML`, `XML`, `TOML`, `CSV`, `MARKDOWN`, `TEXT`; lowercase `.value` |
| `CounterBackend` | String enum with `TIKTOKEN = "tiktoken"` |
| `__version__` | Version generated at package build; falls back to `"0.0.0"` if importing the generated version fails |

See the rendered [public API](api/index.md). Strategy classes, `SmeltContext`,
and registry helpers live in internal modules; they are not root exports.

## Function signatures

The following signatures summarize the supported calls; `parsed` must contain
JSON-compatible dictionaries/lists with string keys.

```text
smelt(text=None, strategies=None, preset=None, *, parsed=None) -> SmeltReport
check(text=None, *, parsed=None) -> SmeltReport
count(text, model="o200k_base") -> int
```

- `text` is a string; `parsed` is a dict/list. If both are given, `parsed` wins.
- Without either input, `smelt()` and `check()` raise `ValueError`.
  An explicit empty string is valid and counts as zero tokens.
- Parsed input is serialized with compact separators, Unicode characters intact,
  and insertion-order keys. That serialization is `report.original` and the
  savings baseline. Passing a parsed object does not measure the whitespace
  removed when its original file was parsed.
- A nonempty `strategies` list takes precedence over `preset`.
  `strategies=[]` falls back to the preset, or `safe`; it does not disable compaction.
  Unknown selected names raise `ValueError`.
- `smelt` and `check` use `o200k_base`; they have no `model` parameter.
- Neither function writes an input file or mutates the caller's dictionary.
  Use the returned string explicitly.

## SmeltReport

| Field | Type | `smelt` | `check` |
|---|---|---|---|
| `original` | `str` | Working input text | Working input text |
| `compacted` | `str` | Accepted pipeline output | Same as `original` |
| `original_tokens` | `int` | Input count | Input count |
| `compacted_tokens` | `int` | Output count | Same as `original_tokens` |
| `savings_pct` | `float` | Actual cumulative reduction | Projected reduction of the **safe** pipeline |
| `format` | `Format` | Detected **input** format | Detected input format |
| `strategies_applied` | `list[str]` | Accepted transforms, in order | Empty list |
| `strategy_estimates` | `dict[str, float]` | Empty mapping | Positive isolated reductions, rounded to two decimals |
| `counter_backend` | `CounterBackend` | `TIKTOKEN` | `TIKTOKEN` |

Thus `check().savings_pct` is not calculated from its unchanged
`compacted_tokens`. Estimates cannot be added together. A strategy can appear
in `strategies_applied` with zero token savings if it shortened the text at
equal token count. The `format` field does not certify that the **output** still
parses in that format.

## AXMTool inputs

Tools are registered under `axm.tools` as `smelt`, `smelt_check`, and
`smelt_count`. All tool arguments are keyword-only.

| Input | Tools | Default | Meaning |
|---|---|---|---|
| `data` | All | `""` | Text or JSON-compatible data; `None` fails |
| `input_path` | All | `None` | UTF-8 file path, relative to the executing process |
| `strategies` | `smelt` | `None` | List of registered strategy names |
| `preset` | `smelt` | `None` | Named preset |
| `model` | `smelt_count` | `"o200k_base"` | Requested model/encoding name |

Non-string data bypasses the file/stdin resolver, including an empty dict/list.
For strings: nonempty `data` wins; otherwise an explicit file wins; otherwise
non-interactive stdin is read. A whitespace-only string is nonempty. An empty
file does not fall back to stdin. Interactive/unavailable stdin leaves an empty
string (stdin `OSError` is swallowed); file failures are returned as errors.
Reading a pipe waits for EOF.

Compaction and analysis serialize dict/list inputs in insertion order;
`smelt_count` sorts keys before counting structured data. To compare the same
textual baseline, pass the **same string** to all three tools. Scalars other than
`None` are accepted by the tool implementation, but the documented Python
`parsed=` contract is dict/list; prefer strings for scalar text.

## ToolResult data

On success, `success=True`, a compact human-readable `text`, and these
`data` fields are returned:

| Tool | Data keys |
|---|---|
| `smelt` | `compacted`, `format`, `original_tokens`, `compacted_tokens`, `savings_pct` (rounded to two decimals), `strategies_applied`, `counter_backend` |
| `smelt_check` | `format`, `tokens`, `strategy_estimates` |
| `smelt_count` | `tokens`, `model`, `counter_backend` |

`smelt_check` does **not** expose the Python report's cumulative savings or
backend field. `smelt_count.model` echoes the requested name; it is not proof
of the resolved encoding. The text display also includes character count,
which is not a separate data key.

Tool exceptions become `ToolResult(success=False, error=str(exc))`. This
includes missing files, directories, invalid UTF-8, `data=None`, and unknown
selected strategies/presets. Zero savings is a successful result, not an error.
Unknown keyword arguments are accepted by `**kwargs` and ignored; use the
published inputs rather than relying on typo detection.

## Token counting and failures

Known OpenAI model names use tiktoken's model mapping; raw encoding names are
also accepted. Names beginning with `claude` (case-insensitive) and unknown
names use `o200k_base` as a proxy. Counts are exact for the selected encoding,
not necessarily for the target model, its message framing, or billing.
The backend remains `tiktoken` for proxy counts. There is no LLM request.

Tokenizer initialization may need tiktoken's cached encoding assets; provision
that cache before relying on offline execution. Encoding errors (for example
disallowed special-token strings) propagate from Python and become tool errors.
The strategy loop suppresses only `RecursionError` from a strategy, treating
it as a skipped transform; failures during input preparation or counting can
still propagate. There is no input-size limit or streaming compaction.
