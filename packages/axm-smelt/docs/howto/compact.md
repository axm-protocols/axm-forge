# Compact Data

Choose text input when whitespace is part of the baseline, or parsed JSON
when the object is already in memory.

## Compact text

```python
from axm_smelt import smelt

data = '{\n  "name": "Alice",\n  "age": 30\n}'
report = smelt(data)
print(report.compacted)
print(report.original_tokens, report.compacted_tokens)
print(f"{report.savings_pct:.2f}% saved")
assert report.compacted_tokens <= report.original_tokens
```

The default `safe` preset still changes representation. Review
[format-specific limits](../explanation/strategies.md#minify) for XML, YAML,
and Markdown before using the result in a parser or renderer.

## Compact an existing object

```python
from axm_smelt import smelt

payload = {"name": "Alice", "notes": None}
report = smelt(parsed=payload, strategies=["minify", "drop_nulls"])
assert payload["notes"] is None
print(report.original)   # Compact JSON baseline, before the strategies
print(report.compacted)
```

A nonempty strategy list overrides `preset`; an empty list falls back to
the preset/default. Only accepted transforms appear in `strategies_applied`.
A selection is not a guarantee that each strategy will be applied.

## Save only the compacted text

This example writes a **separate output file** in the current directory:

```python
from pathlib import Path
from axm_smelt import smelt

source = Path("payload.json").read_text(encoding="utf-8")
report = smelt(source)
Path("payload.compacted.txt").write_text(report.compacted, encoding="utf-8")
```

For a JSON consumer, validate the parsed result against the source before
writing it. `moderate` and `aggressive` can change shape, values, and syntax.

## Use the CLI

In an activated environment containing the package (or with `uv run`):

```bash
printf '{"name": "Alice", "notes": null}\n' | axm smelt
axm smelt --input-path ./payload.json --preset moderate --json-output
```

Plain stdout includes a header. JSON output contains the compacted string and
metrics; extract `compacted` if you need just the payload.
See [CLI argument encoding](../reference/cli.md) and [all report fields](../reference/contracts.md#smeltreport).
