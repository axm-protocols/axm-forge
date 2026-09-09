# API reference

`axm-ingot` provides Python imports only: there are no package scripts or
`axm.tools` registrations, so installing it adds no CLI or MCP command.

## Import map

| Import from | Symbols | Contract |
|---|---|---|
| `axm_ingot` | `Member`, `ResolvedWorkspace`, `resolve_workspace`, `find_project_root`, `find_workspace_root` | [Workspace contracts](#resolve_workspace) |
| `axm_ingot` or `axm_ingot.render` | `header`, `labeled_block`, `compact_table`, `truncate`, `format_count`, `format_size` | [Rendering](render.md) |
| `axm_ingot` or `axm_ingot.duration` | `format_duration` | [Duration](duration.md) |
| `axm_ingot` | `console_script`, `tally_outcomes` | [Console and outcomes](helpers.md) |
| `axm_ingot.uv` only | `parse_workspace_members` | [Raw parser](#parse_workspace_members) |
| `axm_ingot.render` only | `render_result`, `record_table` | [Generic rendering](render.md#render_result) |

The root exports 14 symbols. The five suite utilities are internal:
see [suite helpers](suites.md). The [generated API](generated.md) provides
source-derived signatures for the root exports and documented submodule helpers.

## `resolve_workspace`

`resolve_workspace(pyproject_dir: Path) -> ResolvedWorkspace | None`

Resolves the supplied directory, reads its pyproject, expands
`[tool.uv.workspace].members` globs and subtracts `exclude` globs. Results
are deduplicated by resolved path and sorted by directory basename. Only
directories containing a `pyproject.toml` file are included.

This function does **not** search ancestors. A missing/unreadable/non-UTF-8 or
malformed root pyproject, or an absent workspace table, yields `None`. An
empty workspace table yields a record with an empty member tuple. Invalid
member/exclude types are ignored; only strings in lists are expanded.

The member's pyproject is checked for existence, not parsed. No dependency
graph, package-name validation or uv lock resolution is performed. Paths
reached via symlinks or `..` may lie outside the root; this is not a path
containment check. Sorting by basename does not specify ordering among members
with identical names.

Reading the pyproject catches `OSError` and `ValueError`; glob expansion
skips patterns rejected with `NotImplementedError` or `ValueError`.
Other filesystem/path-resolution errors and invalid argument types can escape.

## `find_workspace_root`

`find_workspace_root(path: Path) -> Path | None`

Walk the resolved path and its ancestors, returning the first directory with
a readable pyproject containing a dictionary at `[tool.uv.workspace]`.
An empty table qualifies; members need not resolve. Unreadable or malformed
pyprojects are skipped. Return `None` when none qualifies.

## `find_project_root`

`find_project_root(start: Path) -> Path`

Resolve `start`, use its parent if it is an existing file, then find the
nearest ancestor containing any `pyproject.toml` file. The file need not
contain valid TOML. Without one, return the resolved starting directory
(or the file's parent). A returned Path therefore does not itself prove a
project exists. Path-operation exceptions can still propagate.

## `parse_workspace_members`

`parse_workspace_members(text: str) -> list[str]`

```python
from axm_ingot.uv import parse_workspace_members

assert parse_workspace_members(
    '[tool.uv.workspace]\nmembers = ["packages/*", 3]\n'
) == ["packages/*"]
```

Parses text with `tomllib.loads`. Returns string entries verbatim, including
duplicates and empty strings. No glob expansion, excludes, filesystem access
or member validation. Malformed TOML or absent/wrongly typed configuration
yields `[]`. The input must be a string; this is not an arbitrary-object API.

## `ResolvedWorkspace`

```python
from dataclasses import dataclass
from pathlib import Path
from axm_ingot import Member

# Shape of the exported frozen record:
@dataclass(frozen=True)
class ResolvedWorkspace:
    root: Path
    members: tuple[Member, ...]
```

Resolver-produced records contain an absolute root and members sorted by name.

## `Member`

A frozen dataclass with `name: str` and `path: Path`. For resolver-produced
values, name is the **directory basename**, not `[project].name`, and path
is absolute and resolved. Two members can share a name; use paths as keys when
uniqueness matters. Constructors do not validate or normalize supplied values.
