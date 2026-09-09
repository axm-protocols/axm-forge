# Move a class and verify its caller

This tutorial uses a disposable directory and a small importable package. It demonstrates a preview, the applied move, copied helper and rewritten caller. Python 3.12+ and an environment with `axm-anvil` are required.

## Install

```bash
uv add axm-anvil
uv run axm-anvil --help
```

## Create a disposable project

Run the following in the environment where you installed the package. The temporary directory is removed automatically after the scenario.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import sys

from axm_anvil import MoveTool

with TemporaryDirectory(prefix="anvil-tutorial-") as directory:
    root = Path(directory)
    package = root / "demo"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "models.py").write_text(
        '__all__ = ["User"]\n\n'
        'def _slug(name: str) -> str:\n    return name.lower()\n\n'
        'class User:\n    def __init__(self, name: str) -> None:\n'
        '        self.id = _slug(name)\n'
    )
    (package / "services.py").write_text("__all__ = []\n")
    (package / "client.py").write_text(
        'from demo.models import User\n\n'
        'def user_id():\n    return User("Ada").id\n'
    )
    before = {p: p.read_bytes() for p in package.glob("*.py")}
    request = dict(
        path=str(root), from_file="demo/models.py",
        to_file="demo/services.py", symbols="User", strict=True,
    )
    tool = MoveTool()
    preview = tool.execute(**request, check=True)
    assert preview.success, preview.error
    assert before == {p: p.read_bytes() for p in before}
    print(preview.text)

    applied = tool.execute(**request)
    assert applied.success, applied.error
    print(applied.data["warnings"])
    assert "class User" not in (package / "models.py").read_text()
    assert "class User" in (package / "services.py").read_text()
    subprocess.run(
        [sys.executable, "-c",
         'from demo.client import user_id; assert user_id() == "ada"'],
        cwd=root, check=True,
    )
```

The caller still returns `ada` after import rewriting. `User` and its `_slug` dependency move to `services.py`; existing literal `__all__` entries are synchronized. Ruff may format the resulting files; if unavailable it is reported as a warning and the move still succeeds.

## Use the dedicated CLI on your project

With existing source and destination files, preview with:

```bash
uv run axm-anvil move src/mylib/models.py src/mylib/services.py User \
    --path . --check --strict
```

The command's paths are illustrative, not files created by the temporary tutorial. `--check` enforces cycle detection without applying edits; `--dry-run` alone is a preview without that enforcement.

Continue with [recipes](../howto/index.md), [rename/extract](../howto/mcp.md), or the [review workflow](../howto/review.md).
