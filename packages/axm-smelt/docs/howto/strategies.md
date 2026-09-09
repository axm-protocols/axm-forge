# Use Strategies

Pass registered names as a Python list, or as one JSON-encoded CLI argument.
Read the [catalog](../explanation/strategies.md) for fidelity and format limits.

## Select a small pipeline

```bash
printf '{"a": 1, "b": null, "c": ""}\n' | axm smelt --strategies '["minify", "drop_nulls"]'
```

```python
from axm_smelt import smelt

report = smelt(
    '{"a": 1, "b": null, "c": ""}',
    strategies=["minify", "drop_nulls"],
)
assert report.compacted == '{"a":1}'
print(report.strategies_applied)
```

The list's order matters. The report lists only candidates accepted by the
token/length guard, so selecting `minify` does not guarantee it appears.

## JSON transformations

The examples below are independent inputs in one script:

```python
from axm_smelt import smelt

cases = [
    ('{"a": 1, "b": 2}', ["minify"]),
    ('{"a": {"b": 1}}', ["flatten"]),
    ('[{"name":"Alice","age":30},{"name":"Bob","age":25}]', ["tabular"]),
    ('{"name": "Alice"}', ["strip_quotes"]),
    ('{"x": 3.14159265}', ["round_numbers"]),
]
for data, strategies in cases:
    report = smelt(data, strategies=strategies)
    print(strategies, report.compacted, report.strategies_applied)
```

Flattening can collide with existing dotted keys; tabular output loses cell
types; stripped keys are not standard JSON. Float precision defaults to two
decimal places. The public `smelt` function accepts names, not strategy
instances or per-strategy configuration.

## Repeated strings

Give aliasing enough repetition to compensate for its envelope overhead:

```python
from axm_smelt import smelt

value = "A long repeated description of this record and its context. " * 3
payload = {f"item_{i}": value for i in range(8)}
report = smelt(parsed=payload, strategies=["dedup_values_with_refs"])
print(report.compacted)
assert "dedup_values_with_refs" in report.strategies_applied
```

The output contains `_refs` and `_data`, changing its schema. An existing
top-level `_refs` or `_data` causes aliasing to be skipped. The
[alias contract](../explanation/strategies.md#dedup_values_with_refs) explains
literal collisions and reconstruction.

## Prose and Markdown

```python
from axm_smelt import smelt

text = "# Report\n\n| Name | Value |\n| --- | --- |\n| A | 1 |\n\n<!-- draft note -->\n"
report = smelt(text, strategies=["compact_tables", "strip_html_comments"])
print(report.compacted)
```

`compact_tables` requires a Markdown classification. Comment removal also
applies to plain text. Review the
[backtick-fence limitations](../explanation/strategies.md#collapse_whitespace)
before processing code examples.

## Combine with a file input

```bash
axm smelt --input-path ./payload.json --strategies '["minify", "drop_nulls", "flatten", "tabular"]' --json-output
```

Once a transform emits a table or relaxed syntax, later JSON transforms may
become ineffective. The pipeline preserves the input's format label rather
than re-detecting each intermediate result.
