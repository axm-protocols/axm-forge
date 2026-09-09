# How-To Guides

Task-oriented guides for common workflows.

- [Promote a helper into `axm-ingot`](promote-a-helper.md) — the two gates
  (Rule of Three + light-leaf) and the migration ritual.

- [Migrate a renderer](../how-to/migrate-local-render-to-ingot.md) — preserve
  output semantics while replacing duplicated formatting.
- [Console and outcome helpers](../reference/helpers.md) — look up a script
  or count supplied pytest summary lines.

The workspace recipes below read an existing checkout without modifying it.

## List the members of a uv workspace

```python
from pathlib import Path

from axm_ingot import resolve_workspace

workspace = resolve_workspace(Path("."))
member_paths = [m.path for m in workspace.members] if workspace else []
member_names = [m.name for m in workspace.members] if workspace else []
```

## Locate the enclosing workspace from a nested directory

```python
from pathlib import Path

from axm_ingot import find_workspace_root

root = find_workspace_root(Path("packages/some-pkg/src"))
```

## Choose the right root

`resolve_workspace` examines exactly the directory passed to it; call
`find_workspace_root` first when starting inside a member. If you want the
nearest project of any kind, use `find_project_root` instead. That helper falls
back to its starting directory when no project exists; it is not an existence
check. See the [workspace contracts](../reference/api.md#resolve_workspace)
for malformed configuration and duplicate-name behavior.
