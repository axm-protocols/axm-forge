# Format Detection

Detection chooses which transformations can apply; it is not a format validator
and does not certify output syntax.

## Probe order

The first matching probe wins, in this exact order:

| Order | Result | Test |
|---|---|---|
| 1 | JSON | Starts with `{` or `[` after trimming, and `json.loads` succeeds |
| 2 | XML | XML declaration or an XML-looking root outside the known HTML-tag set; no XML parse |
| 3 | YAML | YAML indicator pattern, and `yaml.safe_load` returns a dict/list |
| 4 | Markdown | Indicator score reaches two |
| 5 | TOML | `tomllib.loads` returns a nonempty mapping |
| 6 | CSV | Sniffed delimiter and at least two nonempty rows with equal width of at least two columns |
| 7 | Text | Fallback, including empty/whitespace-only input |

Markdown scores two for multiple heading levels, two for a pipe table with
separator, one for a heading level, one for a pair of recognized backtick-fence
lines, and one for a Markdown link. A single heading or fenced block alone may
therefore be labelled text.

CSV sniffing considers comma, semicolon, tab, and pipe. XML excludes strings
starting with `<!`, including a leading DOCTYPE; the heuristic does not check
balanced tags. Malformed JSON falls through to later probes, rather than
automatically receiving the JSON label. JSON scalars are not classified by the
initial object/array probe.

## Format and transformations

| Input | Relevant transformations |
|---|---|
| JSON objects/arrays | `minify`, `drop_nulls`, `flatten`, `tabular`, `dedup_values_with_refs`, `round_numbers`, `strip_quotes` |
| YAML | `minify` |
| XML | `minify` |
| Markdown | `collapse_whitespace`, `compact_tables`, `strip_html_comments` |
| Text | `collapse_whitespace`, `strip_html_comments` |
| TOML / CSV | No dedicated compactor; detected to avoid prose whitespace transformations |

This table covers ordinary object/array and prose inputs. Some JSON-aware
strategies also attempt to parse their text or reuse an available parsed value;
they are not all gated solely by the format enum. Detection does not mean a
strategy will save tokens. Every candidate still passes the
[acceptance guard](architecture.md#acceptance-is-local-and-greedy).

## Inspect the input label

```python
from axm_smelt import Format, smelt

report = smelt('{"a": 1}')
assert report.format is Format.JSON
print(report.format.value)  # json
```

The label is retained across transformations. In particular, `tabular` and
`strip_quotes` can make output invalid JSON without changing `report.format`.
Read the [strategy contracts and fidelity limits](strategies.md) before deciding
whether the result can be passed to another parser.
