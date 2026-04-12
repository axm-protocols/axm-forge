# Hooks Reference

Protocol hooks registered via `axm.hooks` entry points in `axm_ast.hooks.impact`.

---

## `ImpactHook`

```python
from axm_ast.hooks.impact import ImpactHook
```

Entry point: `ast:impact`

Run blast-radius analysis on one or more symbols. When the `symbol` parameter
contains newline characters each line is analyzed separately and results are
merged with max-score semantics.

### `execute(context, **params) -> HookResult`

| Parameter | Type | Required | Description |
|---|---|---|---|
| `context["working_dir"]` | `str` | fallback | Working directory (used when `path` is absent) |
| `symbol` | `str` | yes | Symbol name(s) to analyze — newline-separated for batch |
| `path` | `str` | no | Override working directory |
| `exclude_tests` | `bool` | no | Exclude test files from results (default `False`) |
| `detail` | `str \| None` | no | `"compact"` for markdown table output |

Returns `HookResult` with `impact` dict and `packages` string in metadata.

---

## `DocImpactHook`

```python
from axm_ast.hooks.impact import DocImpactHook
```

Entry point: `ast:doc-impact`

Run documentation-impact analysis on one or more symbols. Returns which
symbols lack docstrings, have stale signatures, or reference external docs.

### `execute(context, **params) -> HookResult`

| Parameter | Type | Required | Description |
|---|---|---|---|
| `context["working_dir"]` | `str` | fallback | Working directory (used when `path` is absent) |
| `symbol` | `str` | yes | Symbol name(s) to analyze — newline-separated for batch |
| `path` | `str` | no | Override working directory |

Returns `HookResult` with `doc_refs`, `undocumented`, and `stale_signatures` in metadata.

---

## `_merge_impact_reports`

```python
from axm_ast.hooks.impact import _merge_impact_reports
```

> Internal helper — prefixed with `_` and excluded from `__all__`.

```python
_merge_impact_reports(symbol: str, reports: list[dict[str, Any]]) -> dict[str, Any]
```

Merge multiple per-symbol impact reports into a single result using
max-score semantics. Deduplicates `affected_modules` and `test_files`.

| Parameter | Type | Description |
|---|---|---|
| `symbol` | `str` | Original (possibly multi-line) symbol string |
| `reports` | `list[dict[str, Any]]` | Individual impact analysis dicts |

Returns a single merged impact dict.
