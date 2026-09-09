# axm-anvil

**CST-based refactoring for top-level Python symbols.**

<p align="center">
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-anvil/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-anvil/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-anvil/coverage.json" alt="Coverage"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
</p>

Move definitions, rename them in place, or extract them into another module.
Anvil uses libcst for transformations, axm-ast for analysis and axm-edit for
batched writes. It changes files; it does not prove semantic equivalence.

| Operation | Generic CLI / MCP | Dedicated CLI |
|---|---|---|
| Move into an existing module | `anvil_move` | `axm-anvil move` |
| Rename in place | `anvil_rename` | — |
| Extract, creating a missing target | `anvil_extract` | — |

## Install and preview

Python 3.12+ is required.

```bash
uv add axm-anvil
uv run axm-anvil --help
```

For existing project files (illustrative paths), preview with cycle enforcement:

```bash
uv run axm-anvil move src/mylib/models.py src/mylib/services.py UserService \
    --path . --check --strict
```

Start with the [disposable-file tutorial](docs/tutorials/getting-started.md) for a
complete runnable example. The Python tools return `ToolResult`; core functions
return dataclass plans or raise exceptions. Check success and warnings before
interpreting results.

## Before applying

Use a clean worktree, review the complete diff, then run project tests and import
checks. Batched writes have best-effort rollback, not OS-level multi-file
transactions. Move/extract run optional Ruff cleanup after the batch; formatting
can change and warnings can accompany success. Extract previews temporarily
create a missing target scaffold. There is no Anvil undo token.

- [Contracts](docs/reference/contracts.md): paths, options, results and errors.
- [Recipes](docs/howto/index.md): helpers, placement, re-export, cycle checks.
- [MCP and AXM CLI](docs/howto/mcp.md): rename/extract and JSON results.
- [Guarantees and limits](docs/explanation/limits.md): what requires review.
- [Python API](docs/reference/api/index.md): exported functions, models and tools.

Moves support overload groups, existing literal `__all__` synchronization,
conditional imports, supported module-attribute callers, in-flight renaming and
placement. Shared-helper extraction, split, merge, promote and seal are not
implemented operations.

## Development

From `packages/axm-anvil` in the axm-forge workspace:

```bash
uv run pytest
uv run --group docs mkdocs build --strict
```

The MkDocs homepage is `docs/index.md`; this README is a separate entry point.

## License

Apache-2.0 — © 2026 AXM Protocols
