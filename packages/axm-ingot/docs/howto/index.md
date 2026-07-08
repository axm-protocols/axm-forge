# How-To Guides

Task-oriented guides for common workflows.

- [Promote a helper into `axm-ingot`](promote-a-helper.md) — the two gates
  (Rule of Three + light-leaf) and the migration ritual.

Two quick recipes inline below; the promotion ritual has its own page above.

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
