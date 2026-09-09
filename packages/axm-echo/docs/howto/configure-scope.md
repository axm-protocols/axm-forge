# Configure the echo scope

Both tools (`echo_code`, `echo_check`) and the corpus extractor
(`extract_monorepo`) scan a **scope**: the set of workspace roots whose
packages make up the corpus. Everything the tools report depends on it, so
check the resolved scope before interpreting a report.

The scope is read from the shared `~/.axm/config.toml` `[echo]` section via
[axm-config](https://pypi.org/project/axm-config/) (resolution order
`env > file > default`). If nothing is configured, the scope **degrades
gracefully** to the current working directory as a single root. Errors while reading configuration
are swallowed; path expansion/resolution and later filesystem traversal can
still fail.

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
from axm_echo import load_scope

for root in load_scope():
    print(root)
```

## Option 2 — the environment variable (per-invocation)

Set `AXM_ECHO_WORKSPACE_ROOTS` to override the file for a single run. The value
is an `os.pathsep`-separated list (`:` on Linux/macOS, `;` on Windows):

```bash
AXM_ECHO_WORKSPACE_ROOTS="$HOME/axm-workspaces/axm-forge:$HOME/axm-workspaces/axm-nexus" \\
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
- `<root>` itself — only when no package children were discovered and the root
  carries a package marker

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

- Mixed arrays retain string entries and skip other types. An empty string
  in a TOML array resolves to the current directory; empty environment-list
  segments are discarded. Use explicit nonempty paths.
- Relative paths resolve against the process working directory, not the
  configuration file's directory. Roots are expanded, resolved and deduplicated.
- Only Python source files are extracted. Public functions/classes follow
  module exports or non-underscore names; this is not a package-root API audit.
- The first resolved root owns [acknowledgements](review-clusters.md).
  Scope order therefore affects waiver ownership even though package discovery
  sorts its final list.

Echo uses axm-config's generic store at `~/.axm/config.toml`;
`AXM_HOME` does not redirect that store. An explicit
`AXM_ECHO_WORKSPACE_ROOTS` overrides this value without changing the file.
For an isolated test, prefer `extract_package(Path(...))` on a temporary
package, or isolate the actual home/config lookup as well as the scan roots.
