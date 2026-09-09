# Architecture

## Overview

`axm-ingot` holds shared helpers used by several packages. Its runtime
dependency list is empty: all implementations use the standard library.
Consumers depend on this library without importing each other's tool layers.

## Module map

| Module | Responsibility | I/O |
|---|---|---|
| `axm_ingot.uv.models` | Frozen `Member`, `ResolvedWorkspace` dataclasses | None |
| `axm_ingot.uv.resolve` | Parse workspace declarations, resolve globs, discover roots | Reads paths and pyprojects; text parser has no I/O |
| `axm_ingot.render` | Compact text primitives and generic renderer | None for ordinary values |
| `axm_ingot.duration` | Milliseconds to short duration text | None |
| `axm_ingot.console` | Locate a console script beside Python or on PATH | File lookup only |
| `axm_ingot.pytest_tally` | Classify supplied outcome lines | Consumes iterable, no pytest execution |
| `axm_ingot.suite` | Internal suite naming and discovery | Reads directories and pyproject |

The [API index](../reference/api.md) distinguishes root exports from documented
submodule imports. Suite helpers are internal Python utilities, not root exports.

## Design decisions

| Decision | Rationale |
|---|---|
| Zero third-party runtime dependencies | A small consumer does not inherit a tool framework or heavy library |
| Frozen dataclasses | Typed records without a model dependency |
| Directory-based workspace members | Resolution does not need to parse every member's package metadata |
| Separate project and workspace discovery | The nearest project is often a member rather than the workspace root |
| Rendering stays independent of `ToolResult` | Callers supply data and decide how to expose or persist the resulting text |

Frozen dataclasses prevent field reassignment, but do not validate constructor
arguments. Absolute paths and sorted members describe resolver-produced values,
not invariants enforced when a caller constructs records manually.

## Boundaries and failure behavior

There is no package-wide purity or never-raises contract. File discovery reads
the live filesystem and can race with concurrent changes. Parsing catches
specific errors; path resolution and user-defined string conversions can fail.

The generic renderer catches ordinary exceptions while formatting its body
and returns its header alone. It does not signal that content was dropped.
Its readable separators and yes/no conversion are not reversible serialization;
retain the structured data when exact types and values matter.

Sharing primitive tests does not replace consumer tests: keep checks of the
consumer's field mapping, error handling and integration. The
[promotion guide](../howto/promote-a-helper.md) explains how to remove duplication
without losing those scenarios.
