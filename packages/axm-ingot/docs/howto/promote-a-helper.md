# Promote a helper into `axm-ingot`

`axm-ingot` grows by **promotion**: a helper does not start here, it *earns* its
way in once it is duplicated across the forge and its dependencies are light
enough to keep the leaf a leaf. This guide is the operational ritual — the two
gates a candidate must clear, and the mechanical steps to move it in and retire
the copies.

## The two gates

A helper may be promoted **only if it clears both** gates. The Rule of Three is
*necessary but not sufficient* — the dependency gate is the second lock.

1. **Rule of Three (reuse gate)** — the same logic is copy-pasted, with the same
   intent, in **at least two** packages (a third consumer is imminent or already
   wants it). One consumer is not a shared helper; it is that package's own code.
2. **Dependency gate (light-leaf gate)** — the helper's dependencies are
   **stdlib only**. `axm-ingot` is imported across the whole galaxy; every
   consumer inherits *all* of its dependencies, so `dependencies` stays
   empty. A helper that needs `httpx`, `pandas`, an SDK — *or* Pydantic — does
   **not** come here. Keep it `reuse_in_place` (import it from the owning
   package) or give it a **thematic light lib** of its own (e.g. an `axm-net`
   for resilient HTTP).

!!! warning "No Pydantic"
    Even though Pydantic is a near-universal AXM dependency, it is a
    *dependency*: adding it to `axm-ingot` breaks the leaf invariant. Value
    objects here are stdlib `@dataclass(frozen=True)`, not `BaseModel`. See
    [Architecture — Design Decisions](../explanation/architecture.md).

## Checklist

Before opening the PR, confirm every box:

- [ ] **Two+ real consumers** copy-paste the logic today (Rule of Three).
- [ ] **Stdlib-only** dependencies — nothing new enters `dependencies` (it stays `[]`).
- [ ] The helper is **pure and defensive** — hostile inputs degrade to
      `None`/`[]`/empty, they never raise. This is the leaf's core contract.
- [ ] A **frozen dataclass** (not Pydantic) for any value object it returns.
- [ ] **Tests move with it** — the helper is tested *here*, once, so consumers
      stop re-testing the primitive.
- [ ] Public symbols are re-exported from `axm_ingot` (or documented as
      `axm_ingot.uv`-only, like `parse_workspace_members`).

## Steps

### 1. Land the helper in `axm-ingot`

Add the function/class to the relevant subpackage (e.g. `axm_ingot.uv`), export
it in that subpackage's `__all__`, and — if it is top-level public — re-export it
from `axm_ingot/__init__.py`. Move the *tests* alongside it (unit under
`tests/unit/`, real-I/O scenarios under `tests/integration/`).

```python
# src/axm_ingot/uv/__init__.py
from axm_ingot.uv.resolve import my_new_helper

__all__ = [..., "my_new_helper"]
```

### 2. Depend on `axm-ingot` from each consumer

In each consuming package's `pyproject.toml`:

```toml
[project]
dependencies = ["axm-ingot"]

[tool.uv.sources]
axm-ingot = { workspace = true }
```

### 3. Migrate the consumers to the shared helper

Replace each copy-pasted implementation with an import:

```python
from axm_ingot.uv import my_new_helper
```

Run each consumer's suite (`uv run --package <consumer> pytest`) — since the
primitive is now tested in `axm-ingot`, the consumer's own tests should only
cover *its* integration, not re-test the helper.

### 4. Delete the source copies

Remove the now-dead local implementations **and their duplicated tests** from
every consumer. This is the payoff: the logic exists once, is tested once, and a
bug fixed here is fixed everywhere.

### 5. Verify the leaf stayed a leaf

Confirm `dependencies = []` is unchanged in `axm-ingot`'s `pyproject.toml`, then
run the workspace gate:

```bash
uv run --package axm-ingot --directory packages/axm-ingot pytest -x -q
```

If the promotion added a runtime dependency, it was the wrong call — revert and
use a thematic light lib instead.
