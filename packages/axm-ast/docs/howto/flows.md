# Trace Execution Flows

The `flows` command traces execution paths from framework entry points through the call graph using BFS.

## Basic Usage

Detect all entry points in a package:

```bash
axm-ast flows src/mylib
```

Trace a specific entry point:

```bash
axm-ast flows src/mylib --entry handle_request
```

## Cross-Module Tracing

Follow calls across package boundaries:

```bash
axm-ast flows src/mylib --entry handle_request --cross-module
```

See [Cross-Module Resolution](../explanation/cross_module_resolution.md) for the algorithm details.

## Source Enrichment

Include function source text in each step:

```bash
axm-ast flows src/mylib --entry handle_request --detail source
```

## Supported Frameworks

Entry point detection uses `_ENTRY_DECORATOR_PREFIXES`, a dispatch table mapping framework names to decorator prefixes. A function is recognized as an entry point when its decorator starts with one of these prefixes.

=== "Cyclopts"

    | Prefix | Example |
    |---|---|
    | `app.default` | `@app.default` |
    | `app.command` | `@app.command("run")` |

=== "Click"

    | Prefix | Example |
    |---|---|
    | `click.command` | `@click.command()` |
    | `click.group` | `@click.group()` |
    | `app.command` | `@app.command()` |

=== "Flask"

    | Prefix | Example |
    |---|---|
    | `app.route` | `@app.route("/api/users")` |
    | `blueprint.route` | `@blueprint.route("/items")` |

=== "FastAPI"

    | Prefix | Example |
    |---|---|
    | `app.get/post/put/delete/patch` | `@app.get("/users")` |
    | `router.get/post/put/delete/patch` | `@router.post("/items")` |

Beyond decorator-based detection, `find_entry_points` also recognizes:

- **Test functions** — `test_*` prefix
- **Main guards** — `if __name__ == "__main__"` blocks
- **`__all__` exports**

!!! tip "Adding a new framework"
    Add a new key to `_ENTRY_DECORATOR_PREFIXES` in `core/flows.py`. The key is the framework name; the value is a list of decorator prefix strings. Matching uses `startswith`, so `"router.get"` matches `@router.get("/path")`.

## Stdlib Filtering

By default, stdlib and builtin callees (e.g. `print`, `len`, `os.path.join`) are excluded from BFS traces to reduce noise. Pass `--no-exclude-stdlib` to include them:

```bash
axm-ast flows src/mylib --entry main --no-exclude-stdlib
```

## Depth Control

Limit BFS depth (default 5):

```bash
axm-ast flows src/mylib --entry main --max-depth 3
```

## JSON Output

```bash
axm-ast flows src/mylib --entry main --json
```
