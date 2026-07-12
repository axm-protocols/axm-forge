# API Reference

`axm-ingot` is a pure library — it exposes **no CLI** and **no MCP tool**. Its
public surface is imported directly from `axm_ingot` (re-exported from
`axm_ingot.uv`).

## `resolve_workspace`

```python
resolve_workspace(pyproject_dir: Path) -> ResolvedWorkspace | None
```

Resolve the uv workspace rooted at `pyproject_dir`. Parses
`[tool.uv.workspace].members`, expands the globs to directories, subtracts the
`exclude` globs, keeps only directories that contain a `pyproject.toml`
(`require_pyproject`), and returns the members sorted by name. Returns `None`
when `pyproject_dir` is not a uv workspace or its pyproject is missing/malformed.

## `find_workspace_root`

```python
find_workspace_root(path: Path) -> Path | None
```

Walk parents from `path` (inclusive) to the first ancestor whose
`pyproject.toml` carries a `[tool.uv.workspace]` section, returning that
directory, else `None`. This targets a **workspace** root specifically — not
merely the first enclosing project `pyproject.toml`.

## `find_project_root`

```python
find_project_root(start: Path) -> Path
```

Walk parents from `start` (inclusive) to the first ancestor containing **any**
`pyproject.toml` — a project root, not necessarily a uv workspace. `start` is
resolved first; a file `start` is anchored on its parent directory. Unlike
[`find_workspace_root`](#find_workspace_root), this **never returns `None`**:
with no `pyproject.toml` in any ancestor it falls back to the (resolved)
starting directory. Use it to anchor relative-import resolution on the nearest
enclosing project rather than on a uv-workspace boundary.

## `parse_workspace_members`

```python
parse_workspace_members(text: str) -> list[str]
```

Pure-string primitive imported from the `axm_ingot.uv` subpackage (it is **not**
re-exported at the top-level `axm_ingot`). Parses `text` with `tomllib.loads`
and returns the declared `[tool.uv.workspace].members` strings **verbatim** — no
glob expansion, no filesystem access, no `exclude` / `require_pyproject`
filtering. Defensive: malformed TOML or an absent `[tool.uv.workspace]` table
yields `[]` rather than raising.

```python
from axm_ingot.uv import parse_workspace_members

parse_workspace_members('[tool.uv.workspace]\nmembers = ["packages/*"]\n')
# ['packages/*']  — raw, unexpanded
```

## `ResolvedWorkspace`

```python
@dataclass(frozen=True)
class ResolvedWorkspace:
    root: Path
    members: tuple[Member, ...]
```

A resolved uv workspace: its absolute `root` and the members sorted by name.

## `Member`

```python
@dataclass(frozen=True)
class Member:
    name: str   # directory basename (NOT [project].name)
    path: Path  # absolute, resolved path
```

A single workspace member. Callers project trivially: `[m.path for m in ...]`
(paths) or `[m.name for m in ...]` (names).

!!! note "`name` is the directory basename, not the package name"
    `Member.name` is the **basename of the member directory**, not the
    `[project].name` declared in the member's own `pyproject.toml`. Two globs
    resolving to same-named directories (e.g. `packages/core` and `libs/core`)
    therefore produce two `Member`s with the same `name`. Callers that index by
    `name` must account for this; when you need the *package* name, read it from
    the member's `pyproject.toml` (its `path` points at the directory).

## Render primitives

The compact `ToolResult.text` primitives (`header`, `labeled_block`,
`compact_table`, `truncate`, `format_count`, `format_size`) are documented on
their own page: [`axm_ingot.render`](render.md).
