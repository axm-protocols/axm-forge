# How-To Guides

Task-oriented guides for common workflows.

## Add a Command to `axm`

To expose a CLI command from your AXM package, add an entry point in your `pyproject.toml`:

```toml
[project.entry-points."axm.commands"]
mycommand = "my_package.cli:my_function"
```

The function must be a valid `cyclopts` command:

```python
# my_package/cli.py
from pathlib import Path

def my_function(path: Path = Path(".")) -> None:
    """My custom AXM command."""
    print(f"Running on {path}")
```

After installing your package, `axm mycommand` will be available automatically.

## Install Specific Plugins

```bash
# Install only what you need
pip install axm[init]        # scaffolding
pip install axm[init,audit]  # scaffolding + quality
pip install axm[all]         # everything
```
