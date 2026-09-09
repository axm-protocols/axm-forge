# Internal suite helpers

These functions are exported by `axm_ingot.suite`, but not by the root
`axm_ingot` package. They support internal AXM tooling; their presence is not
a promise of a stable external API.

## Naming

```python
from axm_ingot.suite import canonical_suite_name, is_suite_name, is_suite_path

assert canonical_suite_name("/work/axm.demo") == "tests_axm_demo"
assert is_suite_name("tests_axm_demo")
assert is_suite_path("tests_axm_demo/unit/test_example.py")
```

`canonical_suite_name(project_root: str | Path) -> str` takes the path's
basename, replaces runs of hyphens/dots with underscores and prefixes
`tests_`. It does not read `[project].name`, lowercase, or resolve the path.

`is_suite_name(name: str) -> bool` accepts `tests` and any `tests_` name
with a nonempty suffix. `is_suite_path(path: str | Path) -> bool` checks
whether any path component has such a name; neither checks existence.

## Discovery

`resolve_suite_dir(project_root: str | Path) -> Path | None` returns the
first direct suite. `resolve_suite_dirs(project_root: str | Path) ->
tuple[Path, ...]` returns all direct suites, followed by suites in resolved
uv-workspace members.

For each project, precedence is:

1. Existing directories from the list
   `[tool.pytest.ini_options].testpaths`, in declared order, deduplicated.
   Paths must resolve within that project. No glob expansion is performed.
2. Its canonical `tests_<directory_name>` directory, if it exists.
3. Its `tests` directory, if it exists.
4. No suite (`None` or an empty tuple).

Any valid configured path suppresses convention fallback, even when its name
does not begin with `tests`. Missing, malformed or non-UTF-8 pyproject content
falls back to convention. Only pyproject config is read, not pytest.ini or
pytest command-line options.

Configured directories are resolved absolute paths; convention fallback uses
the provided root, which can remain relative. The multi-project function
deduplicates by Path equality, so pass an absolute resolved root for consistent
path comparison. Discovery does not guarantee that pytest collects tests there.
