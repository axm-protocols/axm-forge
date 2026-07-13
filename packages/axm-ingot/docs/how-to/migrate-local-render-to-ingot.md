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

## Lessons from the AXM-437 pilot

The first real migration (AXM-437) surfaced four things that are easy to miss.
Apply them on every subsequent port.

### (a) The generic walker is now IN `axm-ingot` — import it, delete the local one

The leaf no longer stops at the six primitives (`header`, `labeled_block`,
`compact_table`, …). The **full compact walker** — the generic
`ToolResult.text` renderer that recurses over an arbitrary `data` dict — was
itself promoted into `axm-ingot` as
[`render_result`](../reference/render.md) (with
[`record_table`](../reference/render.md) for the lossless
homogeneous-record `key | key` table). So a tool that hand-rolled a whole
`render(data)` walker does **not** rebuild it over the leaf primitives: it
imports the walker and deletes its local copy outright.

```python
# tools/render.py  (the whole local walker is gone)
from axm_ingot.render import render_result  # and record_table, if the tool built its own table

def render(data: dict) -> str:
    return render_result("backtest", data)
```

Consequently the anti-duplication check must cover the **whole walker**, not
just the six leaf names. Grepping the consumer for `header(` / `compact_table(`
leaves the copied recursion logic behind. Run the structural similarity check
(`echo_code` / `echo_check`) against `render_result` / `record_table` and
confirm the *entire* local walker — recursion, dispatch, `None`-handling — is
retired, then delete `tools/_render.py` entirely.

### (b) Golden-snapshot terminal-newline convention

Golden `.txt` snapshots must round-trip **byte-identically**, and the pitfall is
the trailing newline. Follow the `axm-weather` `render_snapshot()` convention:
the snapshot helper **MUST append a terminal newline** to the rendered text
before writing (and when asserting), so the golden file ends in `\n` exactly as
an editor / `read_text()` round-trip produces it.

```python
def render_snapshot(text: str) -> str:
    # weather convention: golden .txt files end in a terminal newline
    return text if text.endswith("\n") else text + "\n"
```

Without this, `render_result(...)` (no trailing newline) compared against a
golden file that an editor silently newline-terminated diverges by a single
byte, and the parity check in step 4 fails for a reason that has nothing to do
with the render logic.

### (c) Grep the error-contract before running the suites

Production errors are now **type-prefixed** since the actionable-errors pass:
tools return `f"{type(exc).__name__}: {exc}"`, not the bare `str(exc)`. Any test
that asserts an exact error string with `result.error == "..."` is therefore
**stale** — it encodes the pre-prefix contract and is pre-existing red.

Before running the package suites, grep the tests for exact-match error asserts:

```bash
grep -rn 'result\.error == "' tests/
```

Each hit is a stale exact-match to fix as part of the migration — update it to
the type-prefixed form (or switch to a substring/`in` assertion on the message):

```python
# stale — pre-prefix contract
assert result.error == "file not found"
# fixed — type-prefixed contract
assert result.error == "FileNotFoundError: file not found"
```

These are not regressions introduced by the migration; they are pre-existing red
that the migration is responsible for clearing.

### (d) Shield golden snapshots from mutating pre-commit hooks

Golden `.txt` snapshots must round-trip **byte-identically** (see lesson (b)),
but the whitespace-normalising pre-commit hooks fight that invariant. The
`trailing-whitespace` and `end-of-file-fixer` hooks **rewrite files at commit
time**: they strip trailing spaces and force a single terminal newline. Rendered
output legitimately carries trailing whitespace — an empty value renders as
`key: ` (a key, a colon, a space, then nothing) — so letting these hooks touch a
golden silently mutates the fixture into something the renderer never produces.

Exclude the golden trees from both hooks in `.pre-commit-config.yaml`:

```yaml
  - repo: https://github.com/pre-commit/pre-commit-hooks
    hooks:
      - id: trailing-whitespace
        exclude: tests/fixtures/(snapshots|goldens)/
      - id: end-of-file-fixer
        exclude: tests/fixtures/(snapshots|goldens)/
```

Why this matters beyond a cosmetic diff: a hook that mutates a golden **at commit
time** breaks the **Verdict-Carrying Patch invariant**. The suite is green in the
worktree (the golden on disk matches the renderer), the hook rewrites the golden
as part of the commit, and now the committed tree is **red on `HEAD`** — the
snapshot the reviewer pulls no longer matches the rendered output. The patch
carries a passing verdict that does not survive the commit.

The detection signal is `hook_autofixed_files` in `git_commit`'s `ToolResult`
(added in commit `02da79f3`): when a golden path shows up in that list, a hook
just rewrote a fixture behind your back. Treat any golden appearing there as a
broken verdict — add the `exclude:` above and re-commit rather than accepting the
hook's mutation.
