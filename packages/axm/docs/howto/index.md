# How-to guides

Choose the guide for the operation you want to complete.

- [Write a tool](write-tool.md): publish an `AXMTool` under `axm.tools`
  and invoke it through the generic CLI.
- [Use a tool as a node](tool-node.md): rename inputs, declare writes and
  validate a composition with a scoped substitute.
- [CLI reference](../reference/cli.md): pass structured arguments and collect JSON.

## Add a Command to `axm`

For a request that returns structured data, follow [Write a tool](write-tool.md).
One `axm.tools` declaration supplies the shared discovery path.

Only `axm.tools` entries extend this launcher. Long-running services can
provide their own console script under `project.scripts`.

## Install Specific Plugins

```bash
uv add 'axm[init]'
uv add 'axm[init,audit]'
uv add 'axm[mcp]'
uv add 'axm[all]'
```

All providers must be installed in the environment that runs the launcher.
Installing into a different virtual environment does not extend that catalog.
