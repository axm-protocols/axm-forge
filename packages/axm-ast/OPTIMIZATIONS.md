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

## Roadmap (next candidates)

- **Opt 2 — `find_callers` symbol index.** Replace the O(N) per-query linear
  scan of all call-sites with a cached `symbol → [CallSite]` index (O(1)
  lookup). Big win for repeated/workspace queries.
- **Opt 3 — Cheaper cache fingerprint.** `_file_fingerprint` walks with
  `rglob("*.py")` and stats every file on *every* cache check, descending into
  `.venv`/`.git`/`__pycache__` that analysis itself skips. Make the walk
  consistent with `_discover_py_files`.
- **Opt 4 — Cursor-based AST traversal.** Replace per-node Python recursion +
  `node.children` list allocation in `_visit_calls` with a `TreeCursor` walk
  (same visit order → iso results, less overhead).
