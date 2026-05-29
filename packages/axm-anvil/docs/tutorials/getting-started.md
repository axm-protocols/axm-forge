# Getting Started

This tutorial walks you through installing `axm-anvil` and verifying your setup.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

```bash
uv add axm-anvil
```

Or with pip:

```bash
pip install axm-anvil
```

## Step 1: Verify Installation

```python
from axm_anvil import __version__

print(f"axm-anvil v{__version__}")
```

## Step 2: Run Your First Move

Create two throwaway modules to see a move in action:

```python
# models.py
__all__ = ["User"]


def _slug(name: str) -> str:
    return name.lower()


class User:
    def __init__(self, name: str) -> None:
        self.id = _slug(name)
```

```python
# services.py
__all__ = []
```

Preview the move (nothing is written yet):

```bash
axm-anvil move models.py services.py User --dry-run
```

The plan shows `User` moving, the `_slug` helper being copied along, and the
`__all__` entries being synced. Drop `--dry-run` to apply it atomically. Try
`--rename '{"User": "Account"}'` to rename in flight, or `--no-include-helpers`
to leave `_slug` behind.

## Step 3: Run the Tests

```bash
cd packages/axm-anvil
make check
```

This runs lint + type check + security audit + tests.

## Next Steps

- [How-To Guides](../howto/index.md) — Task-oriented move recipes
- [CLI Reference](../reference/cli.md) — Full command documentation
- [Architecture](../explanation/architecture.md) — How the project is structured
