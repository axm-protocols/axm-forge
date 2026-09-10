# How-to guides

| Goal | Guide |
|---|---|
| Call the tools from an MCP client or shell | [MCP and CLI](mcp.md) |
| Replace a whole file using its current digest | [Guarded rewrite](rewrite.md) |
| Deliberately overwrite an existing file in a batch | [Overwrite with create](#overwrite-with-create) |
| Undo a successful batch or handle an apply failure | [Rollback](rollback.md) |

## Choose the right edit

- Use `replace` for one or more complete lines. Supply the original line
  number when it disambiguates repeated anchors.
- Use `rewrite` for an entire existing file, including quote-heavy prose or
  Python docstrings that the tool's anchor rules reject.
- Use `create` for an absent path. Add `overwrite: true` to that operation only
  when replacing an existing regular file without a checksum guard; use
  `delete` for an existing file you want to remove.
- Use `edit_file` for literal substrings in a single file; it has no batch checkpoint.
- Use `write_file` to create or overwrite a single file without a checksum.

For a multi-file textual rename, collect each complete source line, replace the
name within that line, then submit all changed lines together. This does not
provide semantic rename analysis. See the [operation contract](../reference/batch.md).

## Overwrite with create

Use this recovery when a create was refused because the intended target is an
existing regular file and replacing its current contents unconditionally is
acceptable:

1. Add `"overwrite": true` to that create operation; do not add a global flag.
2. Pass the complete batch to `batch_edit_check` and require `blocking` to be
   `false`. The check does not modify the file.
3. Without changing the filesystem or payload, pass the same batch to
   `batch_edit` and verify both its success result and the final file contents.

```json
{
  "op": "create",
  "file": "notes/status.txt",
  "content": "Ready.\n",
  "overwrite": true
}
```

The apply step revalidates the target. It refuses a directory, a path outside
the project root, or a symbolic link resolving outside it, even if the earlier
check succeeded while the target was a regular file. The permission does not
carry over to later operations.

Prefer [guarded rewrite](rewrite.md) when another writer may change the file
between reading and applying: `create` with `overwrite: true` deliberately has
no checksum and can replace newer contents.

## Search before editing

`search_files` is a bounded discovery tool: at most 50 matches, and matched
lines longer than 500 characters are clipped. Check `truncated` and reread
the source line before using it as an anchor. A clipped line is not valid
`old` content. An empty search result should not be submitted as an empty
batch: the tool rejects empty operations.

For Python symbols, prefer the read-only [axm-ast](https://forge.axm-protocols.io/ast/)
tools. The [filesystem reference](../reference/filesystem.md) details line
ranges, filters and payload shapes.
