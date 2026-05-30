# axm-ast — Performance optimization log

Iterative, equivalence-preserving performance work on the `caller` / `graph`
analysis paths of `axm-ast`.

## Method & guarantees

Every optimization in this log is held to the same bar:

1. **Iso results** — output is byte-for-byte identical to the previous
   revision. Verified by a deterministic SHA-256 *fingerprint* of
   `find_callers()` over **every** symbol of a stable, unmodified sibling
   package (`axm-init`), produced by `benchmarks/bench_callers.py`. The
   fingerprint must not change across an optimization.
2. **Tests green** — `pytest tests/unit` (694) and `pytest tests/integration`
   (868) pass.
3. **Lint & types** — `ruff check` and `mypy` are clean.
4. **Measured** — each change is timed baseline-vs-optimized with the same
   harness (`git stash` toggles the change), reported as *best-of-N* wall
   clock on `axm-ast`'s own source.

Reference equivalence fingerprint (target `axm-init`, 210 call-sites):
`7eea6781c5c9b67d69b9168b8f3508d8d61b722e3c54e9ce8555a5c13d2a79a4`

> Note on the test environment: integration tests spawn temporary git repos;
> the sandbox forces commit signing, which fails for those throw-away repos
> (`git commit` → exit 128) independently of any code change. With
> `commit.gpgsign=false` the full integration suite is green.

Run the benchmark:

```bash
uv run python benchmarks/bench_callers.py            # equivalence target (axm-init)
uv run python benchmarks/bench_callers.py src/axm_ast   # time on axm-ast itself
```

---

## Optimization 1 — Parse-tree cache (kill redundant re-parsing)

**Commit:** `perf(axm-ast): cache parsed trees to drop redundant re-parsing in caller analysis`

**Problem.** Each `.py` file was parsed by tree-sitter multiple times per
session: once in `extract_module_info` (package analysis), then again in
`extract_calls` and `extract_references` (caller / dead-code analysis), each
re-reading the file from disk and re-parsing it.

**Change.** Added an mtime-keyed, thread-safe, bounded-LRU parse cache to
`parse_file` (`core/parser.py`). Repeat parses of an unchanged file are served
from memory; a content change bumps `st_mtime_ns` and forces a re-parse.
`extract_calls` / `extract_references` now go through `parse_file` (the unused
`source_bytes` argument was dropped), and `clear_cache()` also clears the parse
cache.

**Equivalence.** Fingerprint unchanged; 694 unit + 868 integration tests pass;
ruff + mypy clean.

**Benchmark** (best-of, `axm-ast` source, 57 files):

| Scenario | Baseline | Optimized | Gain |
|---|---:|---:|---:|
| Re-extract call-sites (pkg warm) — isolated hot spot | 200.6 ms | 127.2 ms | **−37%** |
| Full cold caller pipeline | 360.3 ms | 281.1 ms | **−22%** |
| Import-graph build (regression guard) | 147.0 ms | 150.7 ms | ~0 |

---

## Optimization 2 — `find_callers` symbol index

**Commit:** `perf(axm-ast): index call-sites by symbol for O(1) find_callers`

**Problem.** `find_callers` flattened every cached call-site and linearly
scanned them for each query (`O(total_call_sites)` per symbol). A tool that
sweeps many symbols (e.g. ranking callers across a package/workspace) paid
`O(symbols × call_sites)`.

**Change.** Added a cached `symbol → [CallSite]` index to `PackageCache`
(`get_call_index`), built once from `get_calls` with insertion order matching
the previous scan order. `find_callers` now does an O(1) dict lookup and
returns a fresh list. The index shares the call-site invalidation lifecycle
(evicted on fingerprint change).

**Equivalence.** Fingerprint unchanged; 1566 tests pass; ruff + mypy clean.

**Benchmark** (best-of-15, `axm-ast` source):

| Scenario | Baseline | Optimized | Gain |
|---|---:|---:|---:|
| `find_callers` × ~625 symbols (warm) | 771.3 ms | 602.1 ms | **−22%** |

> The residual cost is dominated by a per-query cache **fingerprint** check
> (stat-storm), addressed next in Opt 3 — after which the indexed lookup's
> advantage is far larger in relative terms.

---

## Optimization 3 — Cheaper cache fingerprint (pruned scandir walk)

**Commit:** `perf(axm-ast): prune non-source dirs in cache fingerprint walk`

**Problem.** Every cache access (`get` / `get_calls` / `get_call_index`)
re-validates the package by fingerprinting the tree. The old
`_file_fingerprint` used `path.rglob("*.py")` + `Path.stat()`, building `Path`
objects and descending into `.venv`/`.git`/`__pycache__` trees that analysis
itself skips. At ~850 µs/call this dominated the repeated-query path (every
`find_callers` triggers one fingerprint).

**Change.** Added `analyzer.fingerprint_source_tree`: an `os.scandir` walk that
prunes the same `_SKIP_DIRS` / `*.egg-info` directories as `_discover_py_files`
and stores `(path_str, mtime_ns)` pairs. `_file_fingerprint` now delegates to
it. Gitignore is intentionally not replicated (subprocess per dir); an ignored
`.py` outside `_SKIP_DIRS` is simply tracked (errs toward extra invalidation,
never staleness).

**Equivalence.** Fingerprint unchanged; 1566 tests pass; ruff + mypy clean.
Same file set as before (verified), so cache invalidation semantics are
preserved for real source trees.

**Benchmark** (best-of-15, `axm-ast` source):

| Scenario | Baseline | Optimized | Gain |
|---|---:|---:|---:|
| `_file_fingerprint` (micro, 57 files) | 847 µs | 214 µs | **−75%** |
| `find_callers` × ~625 symbols (warm) | 602.5 ms | 214.5 ms | **−64%** |

> Cumulative on the repeated-query path (Opt 2 + Opt 3): **771 ms → 214 ms
> (−72%)**.

---

## Optimization 4 — Iterative AST traversal

**Commit:** `perf(axm-ast): iterative DFS for call/reference visitors`

**Problem.** `_visit_calls` / `_visit_references` recursed once per AST node and
called the defensive `update_context` / `is_call_node` helpers (each doing
`getattr`) on every node. A profile of `extract_calls` showed `_visit_calls` +
the per-node helpers as the dominant self-time, and deep recursion risks
Python's recursion limit on heavily nested code.

**Change.** Rewrote both visitors as explicit-stack DFS. The cheap per-node
checks are inlined on the raw `node.type`, so the public helpers (kept for the
SDK surface / tests) are only paid for the rare def/call nodes that matter.
Visit order is identical (pre-order); references use a set, so order is
irrelevant anyway.

**Equivalence.** Fingerprint unchanged; 1566 tests pass; ruff + mypy clean.

**Benchmark** (best-of, `axm-ast` source):

| Scenario | Baseline | Optimized | Gain |
|---|---:|---:|---:|
| `extract_calls` over all modules (isolated) | 123.5 ms | 115.0 ms | **−7%** |
| Full cold caller pipeline | 297.0 ms | 278.4 ms | **−6%** |

The wall-clock gain is modest — the residual cost is C-level tree-sitter node
access and pydantic `CallSite` construction, not Python call overhead (cProfile
over-weighted the latter). The change also **removes the recursion-depth limit**
on deeply nested ASTs, a robustness win beyond the timing.

---

## Cumulative summary (axm-ast source)

| Path | Before | After | Gain |
|---|---:|---:|---:|
| Full cold caller pipeline | 360 ms | 278 ms | **−23%** |
| Re-extract call-sites (pkg warm) | 200 ms | 121 ms | **−40%** |
| `find_callers` × ~625 symbols (warm) | 771 ms | 215 ms | **−72%** |
| Import-graph build (guard) | 147 ms | 160 ms | ~0 (noise) |

All four optimizations are individually equivalence-checked (identical
`find_callers` fingerprint) and the full 1566-test suite, ruff, and mypy stay
green.

## Roadmap (further candidates, not yet done)

- **Cursor-based traversal** (`tree.walk()`) to avoid `node.children` list
  allocation entirely — larger but riskier than Opt 4.
- **Apply the parse cache to `dead_code` / `flows`**, which still do
  `read_text` + `parse_source` directly.
- **`find_callers_workspace` correctness**: it mutates cached `CallSite.module`
  in place (pre-existing) — should copy before prefixing.
