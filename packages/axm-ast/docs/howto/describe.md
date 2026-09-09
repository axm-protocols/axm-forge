# Describe a Package

Explore a codebase at multiple detail levels depending on your needs.

## Basic Usage

```bash
axm-ast describe src/mylib
```

This shows a **detailed** view: module names, public functions with docstrings and type annotations, and classes.

## Detail Levels

=== "Detailed (default)"

    ```bash
    axm-ast describe src/mylib
    ```

    Shows module names, public function signatures with docstrings, parameters with types, return types, and visibility (🔓/🔒).

=== "Summary"

    ```bash
    axm-ast describe src/mylib --detail summary
    ```

    Quick orientation: module names, public function signatures, and class names only — no docstrings or parameter detail.

=== "Compressed"

    ```bash
    axm-ast describe src/mylib --compress
    ```

    AI-optimized format: signatures + first docstring line + `__all__` + relative imports. No bodies, no absolute imports.

=== "TOC"

    ```bash
    axm-ast describe src/mylib --detail toc --json
    ```

    Table-of-contents view: module names, docstrings, and symbol counts only — no individual function/class details. Use this to decide which modules to drill into.

!!! tip "Budget mode"
    Use `--budget N` to cap the output at the first N lines (intelligent
    truncation). Combine with `--rank` to surface the highest-ranked symbols
    before the cut:

    ```bash
    axm-ast describe src/mylib --budget 10 --rank
    ```

Both text and JSON TOC output support modules without a docstring summary.

## Tool defaults differ

The dedicated CLI defaults to `detailed`; `ast_describe` defaults to `summary`.
Both support `names` for symbol names without signatures. `full` is removed.
For the tool, compression requires `detail="summary"`; the dedicated CLI also
allows its default `detailed`. `--budget` and `--rank` affect normal CLI text,
not TOC, names, JSON or compressed output.

## Ranked Output

Add `--rank` to sort modules and symbols by PageRank importance:

```bash
axm-ast describe src/mylib --rank
```

The most-referenced symbols appear first, making it easy to focus on the core architecture.

## Module Filtering

Filter output to specific modules by name (case-insensitive substring match):

```bash
# Only core modules
axm-ast describe src/mylib --modules core

# Multiple filters (comma-separated)
axm-ast describe src/mylib --modules core,tools

# Combine with TOC for a focused overview
axm-ast describe src/mylib --detail toc --json --modules core
```

## JSON Output

```bash
axm-ast describe src/mylib --json
```

Returns a JSON object with full module, function, class, and import data — ready for programmatic consumption.

## Inspect a Symbol

For detailed inspection of a symbol within a package, use `inspect`:

```bash
# Inspect a function
axm-ast inspect src/mylib --symbol my_function

# Inspect a class method with source code
axm-ast inspect src/mylib --symbol Calculator.add --source

# JSON output with file + line numbers
axm-ast inspect src/mylib --symbol my_function --json

# Inspect by module name — returns module metadata instead of a symbol
axm-ast inspect src/mylib --symbol core.analyzer --json
```

When `--symbol` matches a **module name** rather than an individual symbol, `inspect` falls back to returning module-level metadata: `kind`, `functions`, `classes`, `symbol_count`, `docstring`, and `file`. This is useful for a quick overview of a module without running `describe`.
