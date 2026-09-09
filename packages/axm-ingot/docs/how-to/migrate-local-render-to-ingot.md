# Migrate a local renderer to `axm_ingot.render`

Replace duplicated formatting while preserving the output your consumers
actually rely on. Keep domain-specific field selection in the consuming tool.

## Choose the shared operation

| Existing code | Replacement |
|---|---|
| Header, indentation, padded columns | `header`, `labeled_block`, `compact_table` |
| Recursive display of a payload | `render_result` |
| Selected columns of dictionary records | `record_table` |

Read the [render contracts](../reference/render.md) first. A generic walker
does not automatically match a custom renderer: `None`, booleans, ordering,
whitespace and nested values can differ.

## Add the dependency

Merge these entries into the consumer's existing configuration; preserve its
other dependencies and source mappings:

```toml
[project]
dependencies = ["axm-ingot"]

[tool.uv.sources]
axm-ingot = { workspace = true }
```

The source mapping applies when both packages are uv workspace members.
For a standalone consumer, add the distribution dependency without that mapping.

## Replace primitives while retaining field selection

A complete domain-specific example:

```python
from axm_ingot import compact_table, header, labeled_block

def render_summary(names: list[str], elapsed: str) -> str:
    blocks = [
        header("check", f"{len(names)} files"),
        labeled_block("timing:", [elapsed]),
        compact_table([[name] for name in names], headers=["file"]),
    ]
    return "\n".join(block for block in blocks if block)

assert render_summary(["demo.py"], "1.5s") == (
    "check | 1 files\ntiming:\n  1.5s\nfile\ndemo.py"
)
```

A tool whose local code is a generic recursive walker can instead use:

```python
from axm_ingot.render import render_result

def render(data: dict[str, object]) -> str:
    return render_result("check", data)
```

Do not rebuild the generic walker out of primitives if its existing behavior
is what the consumer needs. Conversely, keep a domain renderer when ordering,
redaction or field selection is part of the contract. Shared rendering does
not sanitize secrets.

## Capture and compare behavior

Before editing, capture the old output for representative fixtures: ordinary
values, empty data, `None`, Unicode, long fields, nested records and errors.
Use the consumer's real imports and its fixture directory. Compare the new
output to those exact expectations, then run the consumer's relevant tests.

A passing fixture proves parity for that fixture, not for every input. Review
each difference rather than weakening assertions automatically. Error text is
owned by the consumer; this migration does not establish a universal error
prefix or authorize unrelated changes to error tests.

For a regression fixture, choose whether it stores exact output or a
normalized terminal newline, then apply that convention consistently:

```python
from pathlib import Path

def assert_snapshot(text: str, snapshot: Path) -> None:
    # Snapshot stores the exact UTF-8 output, including its newline policy.
    assert text.encode("utf-8") == snapshot.read_bytes()
```

Neither `render_result` nor the composition above adds a terminal newline.
If editors or formatting checks rewrite golden files, configure the
consumer's fixture exclusions and rerun the comparison on the committed
content. Do not assume whitespace is irrelevant to byte-level parity.

## Retire the copies

Delete local primitives or the local walker once callers use the shared
implementation. Remove duplicated primitive tests while retaining checks of
the consumer's field mapping, formatting expectations and failure behavior.
Use structural similarity tooling when needed to confirm the old recursion
or formatting logic was removed completely.
