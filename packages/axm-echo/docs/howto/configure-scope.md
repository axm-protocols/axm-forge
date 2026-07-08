# Configure the echo scope

Both tools (`echo_code`, `echo_check`) and the corpus extractor
(`extract_monorepo`) scan a **scope**: the set of workspace roots whose
packages make up the corpus. Everything the tools report depends on it, so
configuring the scope is the one thing you must do before any real use.

The scope is read from the shared `~/.axm/config.toml` `[echo]` section via
[axm-config](https://pypi.org/project/axm-config/) (resolution order
`env > file > default`). If nothing is configured, the scope **degrades
gracefully** to the current working directory as a single root — never an
error.

## Option 1 — the config file (persistent)

Add an `[echo]` section to `~/.axm/config.toml` listing the workspace roots to
scan. Each entry is a directory holding packages under `packages/<pkg>` (the
monorepo convention) or `other/<pkg>` (the flat layout); `~` is expanded.

```toml
[echo]
workspace_roots = [
    "~/Documents/Code/python/axm-workspaces/axm-forge",
    "~/Documents/Code/python/axm-workspaces/axm-nexus",
]
```

Verify the scope resolves to what you expect:

```python
from axm_echo.scope import load_scope

for root in load_scope():
    print(root)
```

## Option 2 — the environment variable (per-invocation)

Set `AXM_ECHO_WORKSPACE_ROOTS` to override the file for a single run. The value
is an `os.pathsep`-separated list (`:` on Linux/macOS, `;` on Windows):

```bash
export AXM_ECHO_WORKSPACE_ROOTS="$HOME/axm-workspaces/axm-forge:$HOME/axm-workspaces/axm-nexus"
axm echo_code --backend tfidf
```

The env layer wins over the file (axm-config's `env > file > default`), so this
is the way to point echo at a scratch checkout without editing your config.

## How roots become packages

For each configured root, echo discovers packages data-driven (no frozen
list), so a newly added package is in scope the moment it exists:

- `<root>/packages/<pkg>` — the AXM monorepo convention
- `<root>/other/<pkg>` — the flat `other` container
- `<root>/<pkg>` — a root that directly holds packages as children
- `<root>` itself — when the root *is* a single package

A directory only counts as a package when it carries a real marker (a `src/`
directory or a `pyproject.toml`), so doc folders and stray `*.py` scripts are
never mistaken for packages.

## Degradation and troubleshooting

- **No config / unreadable file / ill-typed value** → the scope is `[cwd]`. If
  `echo_code` reports a suspiciously tiny corpus, this is usually why: you are
  scanning only the current directory.
- **A root that does not exist** is silently skipped during discovery.
- **`workspace_roots` must be a TOML array of strings** in the file layer; a
  scalar or mapping is ignored (degrades to cwd). Only the environment layer
  accepts a `pathsep`-separated string.
