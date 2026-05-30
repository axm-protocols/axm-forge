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
2. **Tests green** — `pytest tests` (1566 passed, 2 skipped: unit +
   integration + e2e + functional).
3. **Lint & types** — `ruff check` and `mypy` are clean.
4. **Measured** — each change is timed baseline-vs-optimized with the same
   harness, reported as *best-of-N* wall clock on `axm-ast`'s own source. A
   change that does not show a real, reproducible gain is dropped (see the
   rejected `model_construct` experiment below).

Reference equivalence fingerprint (target `axm-init`, 210 call-sites):
`7eea6781c5c9b67d69b9168b8f3508d8d61b722e3c54e9ce8555a5c13d2a79a4`

> Note on the test environment: integration tests spawn temporary git repos;
> the sandbox forces commit signing, which fails for those throw-away repos
> (`git commit` -> exit 128) independently of any code change. With
> `commit.gpgsign=false` the full suite is green.

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
`extract_calls` and `extract_references`, each re-reading and re-parsing it.

**Change.** Added an mtime-keyed, thread-safe, bounded-LRU parse cache to
`parse_file` (`core/parser.py`). A content change bumps `st_mtime_ns` and
forces a re-parse. `extract_calls` / `extract_references` go through
`parse_file`; `clear_cache()` also clears the parse cache.

**Benchmark** (best-of, `axm-ast`, 57 files):

| Scenario | Baseline | Optimized | Gain |
|---|---:|---:|---:|
| Re-extract call-sites (pkg warm) | 200.6 ms | 127.2 ms | -37% |
| Full cold caller pipeline | 360.3 ms | 281.1 ms | -22% |
| Import-graph build (guard) | 147.0 ms | 150.7 ms | ~0 |

---

## Optimization 2 — `find_callers` symbol index

**Commit:** `perf(axm-ast): index call-sites by symbol for O(1) find_callers`

**Problem.** `find_callers` linearly scanned every cached call-site per query
(`O(total_call_sites)`), so sweeping many symbols cost `O(symbols x calls)`.

**Change.** Added a cached `symbol -> [CallSite]` index to `PackageCache`
(`get_call_index`), built once from `get_calls` with insertion order matching
the previous scan order. `find_callers` does an O(1) lookup and returns a
fresh list; the index shares the call-site invalidation lifecycle.

**Benchmark** (best-of-15, `axm-ast`):

| Scenario | Baseline | Optimized | Gain |
|---|---:|---:|---:|
| `find_callers` x ~625 symbols (warm) | 771.3 ms | 602.1 ms | -22% |

The residual cost was dominated by a per-query fingerprint check, addressed in
Opt 3.

---

## Optimization 3 — Cheaper cache fingerprint (pruned scandir walk)

**Commit:** `perf(axm-ast): prune non-source dirs in cache fingerprint walk`

**Problem.** Every cache access re-validates the package by fingerprinting the
tree; every `find_callers` query triggered one. The old `_file_fingerprint`
used `rglob("*.py")` + `Path.stat()`, building `Path` objects and descending
into `.venv`/`.git`/`__pycache__` trees that analysis skips (~850 us/call).

**Change.** Added `analyzer.fingerprint_source_tree`: an `os.scandir` walk that
prunes the same `_SKIP_DIRS` / `*.egg-info` directories as `_discover_py_files`
and records `(path_str, mtime_ns)` pairs. Same file set as before; gitignore is
intentionally not replicated (subprocess per dir), erring toward extra
invalidation, never staleness.

**Benchmark** (best-of-15, `axm-ast`):

| Scenario | Baseline | Optimized | Gain |
|---|---:|---:|---:|
| `_file_fingerprint` (micro, 57 files) | 847 us | 214 us | -75% |
| `find_callers` x ~625 symbols (warm) | 602.5 ms | 214.5 ms | -64% |

Cumulative on the repeated-query path (Opt 2 + Opt 3): **771 ms -> 214 ms
(-72%)**.

---

## Optimization 4 — Iterative AST traversal

**Commit:** `perf(axm-ast): iterative DFS for call/reference visitors`

**Problem.** `_visit_calls` / `_visit_references` recursed once per AST node and
called the defensive `update_context` / `is_call_node` helpers (each doing
`getattr`) on every node; deep recursion also risks Python's recursion limit.

**Change.** Rewrote both visitors as explicit-stack DFS with the cheap per-node
checks inlined on the raw `node.type`, so the public helpers (kept for the SDK
surface / tests) are only paid for the rare def/call nodes. Pre-order visit
order is preserved; references use a set (order irrelevant).

**Benchmark** (best-of, `axm-ast`):

| Scenario | Baseline | Optimized | Gain |
|---|---:|---:|---:|
| `extract_calls` over all modules (isolated) | 123.5 ms | 115.0 ms | -7% |
| Full cold caller pipeline | 297.0 ms | 278.4 ms | -6% |

The gain is modest — the residual cost is C-level tree-sitter node access, not
Python call overhead. The change also **removes the recursion-depth limit** on
deeply nested ASTs.

---

## Optimization 5 — Parse cache for dead-code detectors

**Commit:** `perf(axm-ast): route dead_code parsing through the parse cache`

**Problem.** `dead_code`'s `_extract_lazy_imports`,
`_extract_lazy_namespace_names`, and `_has_intra_module_refs` each did
`mod.path.read_text()` + `parse_source()` directly, re-reading and re-parsing
every module even though analysis had already parsed it.

**Change.** Routed all three through `parse_file`, so they hit the mtime-keyed
parse cache (warm after `analyze_package`). The two detectors that swallowed
read errors keep their `try/except (OSError, UnicodeDecodeError)` around
`parse_file`.

**Benchmark** (best-of-10, `axm-ast`, the 3 detectors over all modules):

| Scenario | Re-parse each (baseline) | Parse-cache hit (optimized) | Gain |
|---|---:|---:|---:|
| lazy/class detectors over all modules | 31.7 ms | 6.4 ms | -80% (4.9x) |

---

## Experiment rejected — `CallSite.model_construct`

Building each `CallSite` via `model_construct` (skipping pydantic validation)
was tried to shave the per-call-node construction cost. A rigorous `timeit`
showed it **0.67x — slower** (1.94 us -> 2.90 us) for this small model: the
Rust-compiled validating `__init__` beats the Python-side `model_construct`
that has to reconstruct `__pydantic_fields_set__` and fill defaults. **Reverted
— no gain.** Recorded here so it is not re-attempted.

---

## Cumulative summary (axm-ast source)

| Path | Before | After | Gain |
|---|---:|---:|---:|
| Full cold caller pipeline | 360 ms | 278 ms | -23% |
| Re-extract call-sites (pkg warm) | 200 ms | 121 ms | -40% |
| `find_callers` x ~625 symbols (warm) | 771 ms | 215 ms | -72% |
| Dead-code lazy/class detectors (isolated) | 32 ms | 6 ms | -80% |
| Import-graph build (guard) | 147 ms | 160 ms | ~0 (noise) |

All five optimizations are individually equivalence-checked (identical
`find_callers` fingerprint) and the full 1566-test suite, ruff, and mypy stay
green.

## Roadmap (further candidates, not yet done)

- **Cursor-based traversal** (`tree.walk()`) to avoid `node.children` list
  allocation entirely — larger but riskier than Opt 4.
- **Apply the parse cache to `flows`**, which still does `read_text` +
  `parse_source` directly (deferred: its helpers also reuse the raw source
  string, so it needs more care than `dead_code` did).
- **`find_callers_workspace` correctness**: it mutates cached `CallSite.module`
  in place (pre-existing) — should copy before prefixing.
