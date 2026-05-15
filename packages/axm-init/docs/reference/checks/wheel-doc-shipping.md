# `pyproject.wheel_doc_shipping`

**Category:** `pyproject` &nbsp;·&nbsp; **Weight:** 2

## Invariant

Markdown docs intended to ship inside the built wheel **must** be wired
through `[tool.hatch.build.targets.wheel.force-include]`. Without this
wiring, `hatchling` excludes `docs/*.md` from the wheel and the published
distribution is silently missing them.

## When it fires

The check resolves the expected doc file list in this order:

1. **Explicit opt-in** — `[tool.axm-init.wheel-doc].files` lists the doc
   files to ship. The check fails (ERROR) if any listed file is not
   force-included.
2. **Auto-detection** — when no explicit list is provided, every
   `docs/*.md` file on disk is treated as a shipping candidate. The check
   fails (WARNING) if any auto-detected file is not force-included.
3. **No docs anywhere** — passes silently.

To **opt out** entirely, declare an empty list: `[tool.axm-init.wheel-doc]`
with `files = []`.

## Configuration — `[tool.axm-init.wheel-doc]`

| Key | Type | Default | Description |
|---|---|---|---|
| `files` | `list[str]` | *(auto-detect)* | Explicit list of doc paths (relative to project root) to ship in the wheel. An empty list disables the check. |

## Examples

### Explicit opt-in

Declare exactly which docs ship in the wheel, then wire them through
`force-include`:

```toml
[tool.axm-init.wheel-doc]
files = ["docs/index.md", "docs/quickstart.md"]

[tool.hatch.build.targets.wheel.force-include]
"docs/index.md" = "my_package/docs/index.md"
"docs/quickstart.md" = "my_package/docs/quickstart.md"
```

### Auto-detection

With no `[tool.axm-init.wheel-doc]` block, every `docs/*.md` discovered
on disk is expected to be force-included. For a project with
`docs/index.md` and `docs/api.md`:

```toml
[tool.hatch.build.targets.wheel.force-include]
"docs/index.md" = "my_package/docs/index.md"
"docs/api.md" = "my_package/docs/api.md"
```

If one of the auto-detected files is missing from `force-include`, the
check emits a WARNING with a ready-to-paste fix snippet.

### Opt out

For projects that intentionally do not ship docs inside the wheel:

```toml
[tool.axm-init.wheel-doc]
files = []
```
