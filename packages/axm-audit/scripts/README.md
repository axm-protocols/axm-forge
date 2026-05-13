# Duplicate-test detector — corpus & evaluation

Tooling to maintain a labelled ground-truth corpus for the
`TEST_QUALITY_DUPLICATE_TESTS` rule, and a benchmark script to compare
detector variants against it.

## Why

The duplicate-test detector flags clusters of structurally similar tests so
a human can fold them via parametrize. The rule is heuristic and noisy by
design — over-flagging is preferred over missing real dups. To tune the
noise/recall trade-off we need a labelled corpus and a way to measure the
impact of any rule change before shipping it.

## Files

| Path | Purpose |
|---|---|
| `scripts/build_corpus.py` | Extract labels from git history → write `cases.json` |
| `scripts/eval_rule.py` | Load corpus, run candidate rules, print recall/specificity |
| `tests/fixtures/duplicate_corpus/cases.json` | The corpus itself (flat list of labelled triplets) |

## Corpus schema

Each entry is a single test, located by `(commit, file, test)`, with a
verdict assigned by a human or by an agent that ran the dedup workflow.

```json
{
  "verdict": "real_dup",
  "source": "git_commit:75bb4a8",
  "rationale": "test(axm-audit): parametrize read_coupling_config cases",
  "repo": "axm-forge",
  "commit": "9c43fe3a...",          // parent SHA — file state BEFORE the fold
  "file": "packages/axm-audit/tests/integration/test_coupling_config.py",
  "test": "test_read_coupling_config_custom_threshold"
}
```

Verdicts:
- `real_dup`: the test was folded into a parametrize/merge — the detector
  **must** flag it.
- `false_positive`: the test was in a duplicate cluster, a human looked at
  it during a dedup pass, and chose **not** to fold it — the detector
  **should not** flag it.

The `commit` field is read-only: nothing is checked out. The eval script
loads the file via `git show <commit>:<file>` (object-database read,
worktree untouched). This means the corpus stays valid across branches and
is safe to use while other git operations run.

## Pair-level evaluation semantics

`eval_rule.py` does not score one test in isolation — it scores **pairs**.
For each `(commit, file)` pair shared by two corpus cases:

- both `real_dup` → MUST_CLUSTER (rule should return True)
- anything else (mixed verdicts, or both `false_positive`) → MUST_SEPARATE

A rule is a function `pair_features → bool`. Metrics:

- **Recall** = MUST_CLUSTER pairs the rule clusters / total MUST_CLUSTER
- **Specificity** = MUST_SEPARATE pairs the rule separates / total MUST_SEPARATE

## Running the evaluation

```bash
cd packages/axm-audit
uv run python scripts/eval_rule.py
```

Edit the candidate rules at the bottom of `eval_rule.py`, re-run, compare.
First run resolves and parses every file (~20s); subsequent runs are
near-instant thanks to `lru_cache` on `git show` + AST parse.

## Extending the corpus

There are two complementary ways to add cases.

### 1. Automatic (re-run the extractor)

`build_corpus.py` walks all git commits whose subject mentions
`parametriz` / `merge.*test` / `dedup` and extracts:

- **`real_dup` cases**: tests deleted by a commit that also added a
  `pytest.mark.parametrize` block in the same file (= a real fold).
- **`false_positive` cases**: tests that were in a duplicate cluster
  *before* the dedup commit, are still in a cluster *after*, and live
  in a file the commit modified (= an agent saw them and chose to skip).

Re-run after any new dedup work to extend the corpus automatically:

```bash
cd packages/axm-audit
uv run python scripts/build_corpus.py
```

This rewrites `cases.json` from scratch — your manual additions (see
below) survive only if the script's extraction logic happens to
re-extract them. **For durable manual additions, see option 2.**

### 2. Manual (append a hand-crafted case)

When you spot a case the extractor misses — or want to record a
borderline judgment for posterity — append it directly to `cases.json`.

```json
{
  "verdict": "false_positive",
  "source": "manual:gabriel-2026-05-10",
  "rationale": "Different rule classes; assertions on disjoint fields. Looked twice, kept separate.",
  "repo": "axm-forge",
  "commit": "main",
  "file": "packages/axm-audit/tests/integration/test_pipeline.py",
  "test": "test_broken_project_lower_score"
}
```

Required fields: `verdict`, `source`, `rationale`, `repo`, `commit`,
`file`, `test`. The `commit` can be `main`, a SHA, or a tag — anything
`git show <commit>:<file>` can resolve.

**Recommendations for hand-crafted cases:**

- Set `source` to `manual:<who>-<date>` so it's clear they're not from
  the extractor.
- Write a sharp `rationale` — future-you will read it when the case
  flips verdict and you need to remember why.
- Pin `commit` to a stable ref (a SHA or tag), not `HEAD`/`main`, if
  the test code might change. The case is anchored to a specific
  version of the file.
- Keep a balance of `real_dup` and `false_positive` per file you
  annotate — a file with only `real_dup` cases produces no
  MUST_SEPARATE pairs, so it doesn't help measure specificity.

**Important**: re-running `build_corpus.py` overwrites `cases.json`.
If you've added manual cases, either:

- (a) commit them, then re-run and merge by hand (acceptable for
  occasional additions), or
- (b) keep manual cases in a separate file (e.g.
  `cases_manual.json`) and adapt `eval_rule.py` to load both —
  do this if manual additions become a regular practice.

### 3. Capture skips from a fresh dedup batch

When you run `dedup-tests`, the orchestrator already produces a
report listing every cluster and the action taken (parametrized /
merged / **skipped + justification**). Each `skipped` cluster is
implicitly a set of `false_positive` labels.

To capture them, after the batch finishes:

1. Identify the package commit SHA at which the batch ran (typically
   the SHA before the first dedup commit).
2. For each skipped cluster, append one entry per test with
   `verdict: "false_positive"`, `source: "dedup_batch:<batch-id>"`,
   and the rationale from the agent's report.

This is currently manual — automating it would require parsing
sub-agent reports, which is doable but not yet wired up.

## Workflow recap

```
  ┌──── new dedup commits land in axm-forge ────┐
  │                                             ▼
  │                                  build_corpus.py
  │                                             │
  │                                             ▼
  │                                  cases.json (auto-grown)
  │                                             │
  └─── (manually append hand-crafted) ──┐       │
                                        ▼       ▼
                                  cases.json (final)
                                             │
                            (modify rule in eval_rule.py)
                                             │
                                             ▼
                                  uv run eval_rule.py
                                             │
                                             ▼
                          recall + specificity per rule
                                             │
                                             ▼
                              (validate → ship in detector)
```

## Limitations

- **Recall is bounded by what we've folded historically**: real dups
  nobody ever noticed are not in the corpus. Treat recall as
  "recall over the dups we know about", not absolute.
- **Specificity is bounded by what we've examined**: a `false_positive`
  label means "an agent saw this and skipped"; tests outside any
  detected cluster contribute nothing.
- **The corpus is per-package (axm-audit)**. Adding cases from other
  workspaces (axm-nexus, axm-knowledge) requires extending the `repo`
  field and ensuring those repos are cloned locally.
- **Pair-level eval ignores cluster shape**: the corpus says "these
  two should/shouldn't be clustered", not "these N tests form one
  cluster". A rule that creates many tiny clusters versus one big
  cluster scores the same if the pair memberships match.
