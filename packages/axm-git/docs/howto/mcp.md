# Use CLI and MCP

`axm-git` supplies tools, not a standalone package executable.
Its `axm.tools` entry points are consumed by the generic `axm` CLI and
by `axm-mcp`. Install the package in the environment running the CLI/server.

## CLI

```bash
axm git_preflight --help
axm git_preflight --path . --diff-lines 0
axm git_commit --help
```

Help is safe to inspect; invoking a mutating command is not a preview.
Use each command's help for CLI serialization of lists and booleans.
The [reference](../reference/cli.md) gives the shared Python/MCP arguments.

## MCP

The server may expose a small direct tool set. Tools outside that set remain
reachable through `axm_call`. Example arguments to the façade:

```json
{
  "name": "git_preflight",
  "arguments": {"path": "/absolute/repository", "diff_lines": 0}
}
```

This JSON is a façade request, not Python source. The façade returns the tool's
compact text; direct Python callers receive the `ToolResult` envelope.
Do not parse display text as a stable structured schema.

MCP is an interface to the same implementation: these operations still spawn
Git/gh subprocesses on the server host. A remote server's `path` refers to
its filesystem.

## Results and failures

Python callers should check `result.success` before using success-only keys.
`result.data` can be absent on early failures; `result.error` explains the
failure. Some failures carry partial state, especially commits and tagging.
Follow the relevant recovery guide instead of blindly replaying a batch.

Never invent keyword options. The tool implementations accept `**kwargs`
and can ignore unknown names. In particular,
`git_tag(action="list")` is **not** a listing operation: it can publish a tag.
Use `git_release_diff` for read-only analysis.

The registry contains the tools listed in the [reference](../reference/cli.md).
GitHub authentication metadata comes from `axm.credentials`, independently
of tool dispatch.
