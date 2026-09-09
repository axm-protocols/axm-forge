# Resolve and summarize a workspace

Create a disposable two-package workspace, exclude one member, then render a
short summary. The example writes only inside a temporary directory, which is
removed when the script finishes.

## Install

Use Python 3.12+ in a project or virtual environment:

```bash
uv add axm-ingot
```

Alternatively, install with `pip install axm-ingot` in your virtual environment.

## Run a complete example

Save this as `workspace_demo.py`:

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from axm_ingot import find_project_root, find_workspace_root, resolve_workspace
from axm_ingot.render import render_result

with TemporaryDirectory() as temporary:
    root = Path(temporary).resolve()
    (root / "pyproject.toml").write_text(
        '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        'exclude = ["packages/experimental"]\n',
        encoding="utf-8",
    )
    for name in ("demo", "experimental"):
        member = root / "packages" / name
        member.mkdir(parents=True)
        (member / "pyproject.toml").write_text(
            f'[project]\nname = "{name}-distribution"\n', encoding="utf-8"
        )
    nested = root / "packages" / "demo" / "src"
    nested.mkdir()

    assert find_project_root(nested) == nested.parent
    assert find_workspace_root(nested) == root
    workspace = resolve_workspace(root)
    assert workspace is not None
    assert [member.name for member in workspace.members] == ["demo"]
    print(render_result("workspace", {"members": ["demo"]}))
```

```bash
uv run python workspace_demo.py
```

Expected output:

```text
workspace
members=demo
```

`find_project_root` finds the nearest project. `find_workspace_root` instead
walks to a directory declaring `[tool.uv.workspace]`. Pass that directory to
`resolve_workspace`: it does not search ancestors itself.

The member name is `demo`, from its directory, even though its distribution
name is `demo-distribution`. The resolver requires a member pyproject file to
exist; it does not validate that member's project metadata.

## Continue

Use the [workspace recipes](../howto/index.md) for an existing checkout,
[render reference](../reference/render.md) for formatting contracts, and
[API index](../reference/api.md) for other helpers.
