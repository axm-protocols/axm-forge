# Console lookup and pytest outcomes

Both helpers are exported at the package root. Neither launches a process.

## `console_script`

```python
from axm_ingot import console_script

script = console_script("axm")
```

Signature: `console_script(name: str, *, executable: str | None = None) -> str`.

Lookup order:

1. A file named `name` beside `executable or sys.executable`.
2. `shutil.which(name)` using the current process PATH.
3. The original `name`, unchanged.

The first check is `is_file()`, not an executability test. A returned bare name
does not prove installation; a relative interpreter path can produce a relative
result. No automatic executable suffix is appended. Treat `name` as a trusted
script name: this helper is lookup convenience, not validation of a command.
The override changes the interpreter-side directory only, not PATH.

## `tally_outcomes`

Signature: `tally_outcomes(lines: Iterable[object]) -> dict[str, int]`.

```python
from axm_ingot import tally_outcomes

assert tally_outcomes([
    "FAILED tests/test_a.py", " error tests/test_b.py", "SKIPPED reason", None
]) == {"failed": 1, "error": 1, "skipped": 1, "unknown": 1}
```

All four keys are always present. Each input element increments one bucket.
For strings, the first whitespace-separated token is lowercased and matched
against `failed`, `error`, `skipped`; other strings and nonstrings are unknown.

This counts **lines**, not test cases or summary quantities. A line beginning
`SKIPPED [5]` counts as one; `5 failed`, `PASSED`, `XFAIL` and `SKIPPED[5]`
are unknown. Pass selected outcome lines, not an entire pytest transcript,
when those are the counts you need. An invalid iterable or an iterator that
raises propagates its exception; tolerance applies to elements.
