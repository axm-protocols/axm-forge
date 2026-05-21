# `fix_corpus/` — synthetic fixture corpus for `axm-audit fix`

This directory holds six mini-packages, each crafted to exercise one
or more stages of the `axm-audit fix` pipeline. Tests under
`tests/integration/` and `tests/unit/` consume these via the
`fix_corpus_case` factory (see `conftest.py`).

Each case has the same shape:

```
<case>/
├── input/      # pre-fix layout (with the broken signal)
└── expected/   # post-fix layout (what axm-audit fix --apply should produce)
```

`input/` is a valid (if minimal) Python package: `pyproject.toml`,
`src/<pkg>/`, `tests/{unit,integration,e2e}/`. Total LOC stays under
~200 per case — the point is to cover pipeline branches, not realism.

## The six cases

| Case            | Stage(s) exercised | Signal in `input/`                                                                       |
| --------------- | ------------------ | ---------------------------------------------------------------------------------------- |
| `relocate_only` | relocate           | A pure in-memory test sits in `tests/integration/` and should move to `tests/unit/`.     |
| `rename_only`   | rename             | A test file is named `test_wrong_name.py` but targets `widget.py` (NAME_MISMATCH).       |
| `split_only`    | split              | One file contains two distinct `(test, src_module)` tuples — must split into two files.  |
| `merge_only`    | merge              | Two test files target the same `src_module` — both canonicalise to the same name.        |
| `flatten_only`  | flatten            | A heterogeneous `Test*` class with method-level SUTs that should become free functions.  |
| `mixed`         | all five           | Triggers relocate + split + merge + rename + flatten in a single fix run.                |

The smoke tests in
`tests/unit/core/fix/test_corpus_loader.py` verify that:

- the corpus root contains exactly these six sub-directories, each
  with `input/` and `expected/` sub-trees (AC1);
- `fix_corpus_case("relocate_only")` returns paths to a real temp
  package and the expected tree (AC4, AC8).

Invariant testing (T11) consumes the corpus to check `axm-audit fix`
idempotence (running twice == running once), parity (every stage
applied) and stability against snapshot drift.

## Regenerating `expected/` trees

`expected/` trees are derived from a single known-good run of
`axm-audit fix --apply` against the `input/` tree. To regenerate one
or all cases::

    uv run python tests/fixtures/fix_corpus/regenerate.py <case_name>
    uv run python tests/fixtures/fix_corpus/regenerate.py --all

The script copies `input/` to a temp dir, `git init`s it, runs
`axm-audit fix --apply`, and overwrites `expected/` with the result.
**Commit the corpus before running** so you can diff and review the
new expected tree.

> Until T8 ships the production CLI, the `expected/` trees in this
> directory are hand-crafted from the legacy `tuple_fix_proto.py
> --apply` output. T11 will validate them against the new CLI.

## Why these aren't real tests

Every `input/test_*.py` and `expected/test_*.py` file is fixture
data, not a test pytest should run. The `conftest.py` at this level
declares::

    collect_ignore_glob = ["*/input", "*/expected"]

so `uv run pytest tests/fixtures/` collects zero items (AC7).
