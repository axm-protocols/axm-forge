# Diff, flows and documentation CLI

These commands belong to the dedicated `axm-ast` binary. Return to the [CLI reference](cli.md) for the remaining commands.

## `diff` — Structural Branch Diff

```
axm-ast diff REFS [PATH] [OPTIONS]
```

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `REFS` | | string | *required* | Git refs in `base..head` format |
| `PATH` | | string | `.` | Path to package directory |
| `--json` | | bool | `False` | Output as JSON |

Compares committed git refs at symbol and signature level. Creates and cleans temporary git worktrees, then analyzes each version. Body-only edits with unchanged signatures are not reported as modified symbols; uncommitted changes are not included.

**Example:**

```bash
axm-ast diff main..feature src/mylib
```

```
🔀 Structural diff main..feature — 3 change(s)

  Symbols added (1):
    + new_func (function) — core.py

  Symbols modified (1):
    ~ process (function) — engine.py

  Symbols removed (1):
    - old_helper (function) — utils.py
```

---

## `flows` — Entry Points & Execution Flow Tracing

```
axm-ast flows [OPTIONS] [PATH]
```

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `PATH` | | string | `.` | Path to package directory |
| `--trace` | `-t` | string | *none* | Entry point name to trace BFS flow from |
| `--max-depth` | | int | `5` | Maximum BFS depth for flow tracing |
| `--cross-module` | | bool | `False` | Resolve imports and trace into external modules |
| `--detail` | `-d` | string | `trace` | Detail level: `trace` (names only), `source` (include function source code), or `compact` (tree with box-drawing chars) |
| `--no-exclude-stdlib` | | bool | `False` | Include stdlib/builtin callees in the BFS trace (excluded by default) |
| `--json` | | bool | `False` | Output as JSON |

Without `--trace`, detects entry points (cyclopts, click, Flask, FastAPI, pytest, `__main__`, `__all__` exports). With `--trace`, performs BFS call-graph traversal from the named symbol.

!!! warning "Detail validation"
    Invalid `--detail` values are rejected before tracing begins. The CLI exits with status 1, the AXM tool returns `success=False`.

!!! note "Cross-module resolution"
    With `--cross-module`, the tracer resolves `from X import Y` statements and traces into the target module. When the target is a **sibling package** (e.g. `tests/` importing from `django/`), the tracer walks up to the **project root** (detected via `.git`, `pyproject.toml`, `setup.py`) as a fallback search path.

**Examples:**

```bash
# Detect all entry points
axm-ast flows src/mylib

# Trace BFS flow from an entry point
axm-ast flows src/mylib --trace main

# Cross-module trace with source code
axm-ast flows tests/ --trace test_response --cross-module --detail source

# JSON output for CI/agents
axm-ast flows src/mylib --trace main --json
```

```
🔀 Flow from 'analyze_package' (4 step(s)):

analyze_package  (core.analyzer:71)
├── _discover_py_files  (core.analyzer:123)
├── extract_module_info  (core.analyzer:126)
└── _build_edges  (core.analyzer:129)
```

The tree is rendered by `format_flow_compact` (box-drawing glyphs
`├──`/`└──`, indentation per depth). Cross-module callees resolved with
`--cross-module` are recorded as leaves annotated with their resolved
module, but are not themselves expanded further (single-hop, see the
[cross-module resolution](../explanation/cross_module_resolution.md) page).

---

## `docs` — Documentation Tree Dump

```
axm-ast docs [OPTIONS] [PATH]
```

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `PATH` | | string | `.` | Project root directory |
| `--detail` | `-d` | string | `full` | Detail level: `toc`, `summary`, `full` |
| `--pages` | `-p` | string | *none* | Comma-separated page name substrings to filter |
| `--json` | | bool | `False` | Output as JSON |
| `--tree` | | bool | `False` | Only show directory tree |

### Detail levels

| Level | Returns | Use case |
|---|---|---|
| `toc` | Heading tree + line count per page (~500 tokens) | Quick scan, decide which pages to read |
| `summary` | Headings + first sentence per section | Budget-friendly overview with context |
| `full` | Complete page content (default) | Full doc sync, initial exploration |

**Examples:**

```bash
# Full content (default)
axm-ast docs .

# Heading scan only
axm-ast docs . --detail toc

# Summary with page filter
axm-ast docs . --detail summary --pages architecture,howto

# Tree-only mode
axm-ast docs . --tree
```

---
