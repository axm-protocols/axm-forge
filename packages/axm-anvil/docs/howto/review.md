# Preview, apply and review a refactor

Start in a clean worktree with an explicit root covering all affected packages. Keep a recoverable baseline; Anvil does not return an undo token. The paths below are illustrative and must name existing modules in your project.

```bash
axm-anvil move src/mylib/models.py src/mylib/services.py UserService \
    --path . --check --strict
```

`--check` previews and rejects a detected new import cycle. Review warnings and callers; inspect the Python `MovePlan` texts when a summary is insufficient. `--dry-run` alone does not enforce cycle rejection. To reject helper duplication, add `--shared-helpers error`.

Apply the same request after resolving warnings:

```bash
axm-anvil move src/mylib/models.py src/mylib/services.py UserService \
    --path . --strict --shared-helpers error
```

The request is recomputed, not applied from a saved preview. Avoid simultaneous edits between preview and apply. Review the entire version-control diff, including callers and Ruff changes. For extraction also review callers omitted from `files_modified`. Then run the project's import/collection checks, relevant tests, lint and type checks. A successful tool result means the transformation returned, not that these checks passed.

If apply fails, inspect the touched paths before retrying. Batch rollback is best-effort and Anvil does not expose rollback status; restore only the intended changes from your baseline. A Ruff warning after a successful write leaves the move applied. See [guarantees and limits](../explanation/limits.md).
