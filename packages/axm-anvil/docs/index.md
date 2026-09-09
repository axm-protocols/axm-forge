# axm-anvil

Move, rename and extract top-level Python symbols with libcst transformations. Anvil uses `axm-ast` for code analysis and `axm-edit` for batched writes; it changes files.

| Your goal | Start here |
|---|---|
| Try a complete move on disposable files | [Getting started](tutorials/getting-started.md) |
| Choose move, rename or extract | [Operation contracts](reference/contracts.md) |
| Use the tool from an agent | [MCP and generic AXM CLI](howto/mcp.md) |
| Apply a real refactor | [Review workflow](howto/review.md) |
| Understand rollback and rewriting limits | [Guarantees and limits](explanation/limits.md) |
| Integrate from Python | [Python API](reference/api/index.md) |

Install with `uv add axm-anvil` (Python 3.12+). The dedicated CLI provides `axm-anvil move`; the generic AXM dispatcher exposes `anvil_move`, `anvil_rename` and `anvil_extract` when installed in its environment.

Preview first. A successful result can contain warnings, and a parseable transformation is not proof of unchanged behavior. Move/extract run optional Ruff cleanup **after** batched writes; exact formatting and end-to-end transactional rollback are not guaranteed.
