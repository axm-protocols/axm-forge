# Use Strategies

Apply individual strategies by name via `--strategies` (CLI) or the `strategies` parameter (Python API).

For a full description of each strategy, see the [Strategy Catalog](../explanation/strategies.md).

## minify

Lossless JSON whitespace removal.

```bash
echo '{"a": 1, "b": 2}' | axm-smelt compact --strategies minify
# {"a":1,"b":2}
```

```python
from axm_smelt import smelt
report = smelt('{"a": 1, "b": 2}', strategies=["minify"])
print(report.compacted)  # {"a":1,"b":2}
```

## drop_nulls

Remove `None`, `""`, `[]`, `{}` values from dicts and lists.

```bash
echo '{"a": 1, "b": null, "c": ""}' | axm-smelt compact --strategies minify,drop_nulls
# {"a":1}
```

```python
report = smelt('{"a": 1, "b": null, "c": ""}', strategies=["minify", "drop_nulls"])
print(report.compacted)  # {"a":1}
```

## flatten

Collapse single-child wrapper dicts.

```bash
echo '{"a": {"b": 1}}' | axm-smelt compact --strategies minify,flatten
# {"a.b":1}
```

```python
report = smelt('{"a": {"b": 1}}', strategies=["minify", "flatten"])
print(report.compacted)  # {"a.b":1}
```

## tabular

Convert `list[dict]` JSON to a compact pipe-separated table.

```bash
echo '[{"name":"Alice","age":30},{"name":"Bob","age":25}]' | axm-smelt compact --strategies minify,tabular
```

```python
data = '[{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]'
report = smelt(data, strategies=["minify", "tabular"])
print(report.compacted)
# name|age
# Alice|30
# Bob|25
```

## dedup_values

Replace frequently repeated long string values (>=20 chars, >=2 occurrences) with short aliases.

```python
data = '{"a": "a-very-long-repeated-value", "b": "a-very-long-repeated-value"}'
report = smelt(data, strategies=["minify", "dedup_values"])
# {"_refs":{"$R0":"a-very-long-repeated-value"},"_data":{"a":"$R0","b":"$R0"}}
```

## strip_quotes

Remove quotes on simple alphanumeric JSON keys.

```python
report = smelt('{"name": "Alice"}', strategies=["minify", "strip_quotes"])
print(report.compacted)  # {name:"Alice"}
```

## round_numbers

Round float values to N decimal places (default: 2).

```python
report = smelt('{"x": 3.14159265}', strategies=["minify", "round_numbers"])
print(report.compacted)  # {"x":3.14}
```

## Combining strategies

Strategies are applied in the order provided. Apply `minify` first to normalize JSON before other strategies process it:

```bash
axm-smelt compact --file data.json --strategies minify,drop_nulls,flatten,tabular
```
