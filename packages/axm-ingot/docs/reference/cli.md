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
    name: str   # directory name
    path: Path  # absolute, resolved path
```

A single workspace member. Callers project trivially: `[m.path for m in ...]`
(paths) or `[m.name for m in ...]` (names).

## Python API (auto-generated)

Full auto-generated API reference is available under [Python API](api/).
