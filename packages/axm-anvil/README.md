<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>axm-anvil — CST-based refactoring for top-level Python symbols</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-anvil/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-anvil/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-anvil/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-anvil/"><img src="https://img.shields.io/pypi/v/axm-anvil" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://forge.axm-protocols.io/anvil/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

Move definitions, rename them in place, or extract them into another module.
Anvil uses libcst for transformations, axm-ast for analysis and axm-edit for
batched writes. It changes files; it does not prove semantic equivalence.

## Features

- Move top-level definitions into an existing module, rename them in place,
  or extract them into a new module.
- Preview a move with cycle enforcement before applying it.
- Rewrite supported callers and synchronize existing literal `__all__` entries.
- Handle overload groups, conditional imports, local helpers, in-flight
  renaming and placement.

## Installation

Python 3.12+ is required.

```bash
uv add axm-anvil
uv run axm-anvil --help
```

## Quick Start

From the project environment where you installed Anvil, create disposable files
and preview moving a class:

```bash
anvil_demo=$(mktemp -d)
mkdir "$anvil_demo/demo"
printf '' > "$anvil_demo/demo/__init__.py"
printf 'class User:\n    pass\n' > "$anvil_demo/demo/models.py"
printf '' > "$anvil_demo/demo/services.py"
uv run axm-anvil move demo/models.py demo/services.py User \
    --path "$anvil_demo" --check --strict
```

The command prints a move plan without applying it. The original `User` stays
in `models.py`. The [disposable-file tutorial](docs/tutorials/getting-started.md)
continues through an applied move and checks that a caller still works.

## Usage

| Operation | Generic CLI / MCP | Dedicated CLI |
|---|---|---|
| Move into an existing module | `anvil_move` | `axm-anvil move` |
| Rename in place | `anvil_rename` | — |
| Extract, creating a missing target | `anvil_extract` | — |

### Preview project changes

For existing project files (illustrative paths), preview with cycle enforcement:

```bash
uv run axm-anvil move src/mylib/models.py src/mylib/services.py UserService \
    --path . --check --strict
```

The Python tools return `ToolResult`; core functions return dataclass plans or
raise exceptions. Check success and warnings before interpreting results.

### Before applying

Use a clean worktree, review the complete diff, then run project tests and import
checks. Batched writes have best-effort rollback, not OS-level multi-file
transactions. Move/extract run optional Ruff cleanup after the batch; formatting
can change and warnings can accompany success. Extract previews temporarily
create a missing target scaffold. There is no Anvil undo token.

Moves support overload groups, existing literal `__all__` synchronization,
conditional imports, supported module-attribute callers, in-flight renaming and
placement. Shared-helper extraction, split, merge, promote and seal are not
implemented operations.

## Documentation

- [Published documentation](https://forge.axm-protocols.io/anvil/).
- [Getting started](docs/tutorials/getting-started.md): a complete move scenario.
- [Contracts](docs/reference/contracts.md): paths, options, results and errors.
- [Recipes](docs/howto/index.md): helpers, placement, re-export, cycle checks.
- [MCP and AXM CLI](docs/howto/mcp.md): rename/extract and JSON results.
- [Guarantees and limits](docs/explanation/limits.md): what requires review.
- [Python API](docs/reference/api/index.md): exported functions, models and tools.

## Development

From the axm-forge workspace root:

```bash
uv sync --all-packages --all-groups
uv run --package axm-anvil --directory packages/axm-anvil pytest
uv run --package axm-anvil --directory packages/axm-anvil --group docs mkdocs build --strict
```

The MkDocs homepage is `docs/index.md`; this README is a separate entry point.

## License

Licensed under Apache-2.0. See [LICENSE](LICENSE).
