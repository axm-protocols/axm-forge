# Your first workspace query

This tutorial uses the current checkout to discover a tool and inspect a
package. It does not start an MCP server or edit source files.

## Install the checkout

Use Python 3.12+, uv and Git.

```bash
git clone https://github.com/axm-protocols/axm-forge.git
cd axm-forge
uv sync --all-packages --all-groups
```

The sync installs the workspace members and test/docs tooling. The environment
also includes heavier dependencies such as echo's similarity libraries.

## Discover the CLI

```bash
uv run axm --help
uv run axm ast_context --help
```

The first command lists providers discoverable in this Python environment.
The second shows the actual argument names for the selected tool.
Installing a provider into another environment does not add it to this CLI.

## Inspect a package

```bash
uv run axm ast_context packages/axm-edit --depth 1
```

Expect a structural overview of axm-edit. The query reads the package;
it does not apply edits. Exact counts depend on the checkout.

Now inspect a known public class:

```bash
uv run axm ast_inspect packages/axm --symbol ToolResult
```

The result locates its declaration and describes its interface. Follow the
[SDK guide](../axm/index.md) for result handling and the
[AST documentation](../ast/index.md) for deeper queries.

## Next steps

- [Configure an MCP client](../axm-mcp/tutorials/quickstart.md) to use the same
  tool model through a server.
- [Choose another package](../packages/index.md).
- [Run checks before contributing](../contributing.md).
- [Preview this documentation](../howto/documentation.md).
