# How-to guides

| Goal | Guide |
|---|---|
| Call the tools from an MCP client or shell | [MCP and CLI](mcp.md) |
| Replace a whole file using its current digest | [Guarded rewrite](rewrite.md) |
| Undo a successful batch or handle an apply failure | [Rollback](rollback.md) |

## Choose the right edit

- Use `replace` for one or more complete lines. Supply the original line
  number when it disambiguates repeated anchors.
- Use `rewrite` for an entire existing file, including quote-heavy prose or
  Python docstrings that the tool's anchor rules reject.
- Use `create` only when the path does not exist, and `delete` for an existing file.
- Use `edit_file` for literal substrings in a single file; it has no batch checkpoint.
- Use `write_file` to create or overwrite a single file without a checksum.

For a multi-file textual rename, collect each complete source line, replace the
name within that line, then submit all changed lines together. This does not
provide semantic rename analysis. See the [operation contract](../reference/batch.md).

## Search before editing

`search_files` is a bounded discovery tool: at most 50 matches, and matched
lines longer than 500 characters are clipped. Check `truncated` and reread
the source line before using it as an anchor. A clipped line is not valid
`old` content. An empty search result should not be submitted as an empty
batch: the tool rejects empty operations.

For Python symbols, prefer the read-only [axm-ast](https://forge.axm-protocols.io/ast/)
tools. The [filesystem reference](../reference/filesystem.md) details line
ranges, filters and payload shapes.
