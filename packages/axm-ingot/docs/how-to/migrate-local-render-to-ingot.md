# Migrate a local `tools/_render.py` to `axm_ingot.render`

Many AXM tools grew a private `tools/_render.py` that hand-rolls the compact
`ToolResult.text` — header lines, indented blocks, aligned tables, truncation,
human-readable counts and sizes. Those copies are exactly what
[`axm_ingot.render`](../reference/render.md) was factored out of. This recipe
replaces a local `_render.py` with a **few-line métier renderer** built on the
shared primitives, and proves the swap is byte-for-byte safe.

## Before — a duplicated local renderer

A typical `tools/_render.py` re-implements the primitives inline:

```python
# tools/_render.py  (the copy we want to retire)
def _table(rows, headers):
    matrix = [list(map(str, headers))] + [list(map(str, r)) for r in rows]
    widths = [max(len(row[c]) for row in matrix) for c in range(len(matrix[0]))]
    return "\n".join(
        "  ".join(cell.ljust(widths[c]) for c, cell in enumerate(row)).rstrip()
        for row in matrix
    )


def render(data: dict) -> str:
    head = f"backtest | {data['n_trades']} trades"
    metrics = "metrics:\n" + "\n".join(
        f"  {line}" for line in (
            f"sharpe {data['sharpe']:.2f}",
            f"maxdd  {data['max_drawdown']:.1%}",
        )
    )
    table = _table(
        [[t["symbol"], t["pnl"]] for t in data["trades"]],
        headers=["symbol", "pnl"],
    )
    return "\n".join([head, metrics, table])
```

Every tool that does this carries — and independently bug-fixes — its own
alignment, padding and `None`-handling logic.

## After — a few-line renderer over `axm_ingot.render`

Delete the hand-rolled primitives; keep only the *métier* shaping:

```python
# tools/render.py  (built on the shared leaf)
from axm_ingot.render import compact_table, header, labeled_block


def render(data: dict) -> str:
    blocks = [
        header("backtest", f"{data['n_trades']} trades"),
        labeled_block("metrics:", [
            f"sharpe {data['sharpe']:.2f}",
            f"maxdd  {data['max_drawdown']:.1%}",
        ]),
        compact_table(
            [[t["symbol"], t["pnl"]] for t in data["trades"]],
            headers=["symbol", "pnl"],
        ),
    ]
    return "\n".join(block for block in blocks if block)
```

The renderer now expresses *only* what is specific to this tool — which fields
go where. Alignment, indentation, ragged-row padding and `None`-safety live once
in the leaf. Filtering on `if block` drops empty sections (e.g. an empty
`labeled_block` when there are no metrics) so no dangling label is emitted.

## Steps

### 1. Depend on `axm-ingot`

In the consumer's `pyproject.toml`:

```toml
[project]
dependencies = ["axm-ingot"]

[tool.uv.sources]
axm-ingot = { workspace = true }
```

`axm-ingot` is a stdlib-only leaf, so this adds **no** transitive runtime
dependency.

### 2. Capture the old output (the parity baseline)

Before touching anything, freeze the current renderer's output on a
representative fixture so you can compare against it later:

```bash
uv run --package <consumer> python -c \
  "from tools._render import render; from tests.fixtures.sample import SAMPLE; \
   import sys; sys.stdout.write(render(SAMPLE))" > /tmp/render_before.txt
```

### 3. Rewrite the renderer over the shared primitives

Replace the body of `tools/_render.py` (or add `tools/render.py`) with the
few-line version above, importing from `axm_ingot.render`.

### 4. Byte-parity check

Render the same fixture through the new renderer and diff the bytes against the
frozen baseline:

```bash
uv run --package <consumer> python -c \
  "from tools.render import render; from tests.fixtures.sample import SAMPLE; \
   import sys; sys.stdout.write(render(SAMPLE))" > /tmp/render_after.txt

diff /tmp/render_before.txt /tmp/render_after.txt && echo "byte-parity OK"
```

A clean `diff` (exit 0) proves the migration is behaviour-preserving. If it
differs, the local copy had a quirk (extra trailing space, a different `None`
rendering) — reconcile it in the métier shaping, not by re-adding primitives.

Pin the check as a regression test:

```python
def test_render_matches_baseline():
    from tools.render import render
    from tests.fixtures.sample import SAMPLE

    expected = (Path(__file__).parent / "fixtures" / "render_before.txt").read_text()
    assert render(SAMPLE) == expected
```

### 5. Delete the local primitives

Remove the now-dead `_table`/`_header`/… helpers (and their duplicated tests)
from the consumer. The primitives are tested once, in `axm-ingot`; the
consumer's suite should now only cover *its* field mapping, not re-test the
table aligner.
