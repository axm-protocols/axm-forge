# Write guarantees and semantic limits

## What atomic means here

Anvil renders source, target and discovered callers in memory and parse-validates transformed Python before sending a single batch to `axm-edit`. Batch validation rejects invalid operations before writes. Apply captures a checkpoint of touched paths, then writes files sequentially; an apply exception triggers restoration of those paths. This is **not an OS-level multi-file transaction**: other readers can see intermediate state, process crashes are not covered, and rollback itself can fail.

Anvil's adapter raises from the batch error message but discards its checkpoint, detailed diagnostics and `rollback_failed` field. There is no Anvil undo command or checkpoint in its result. After an apply error inspect the filesystem; recover from your own version-control baseline. Run one refactor at a time in a clean worktree and review the complete diff before committing.

## Post-processing is outside the batch

After a successful move/extract write, Anvil invokes the current interpreter's `ruff` module on source and target: import cleanup/fixes, then formatting and re-parsing. Source unused-import cleanup is skipped for re-export mode. Caller files are not passed to Ruff.

Ruff is optional at runtime. Unavailable Ruff, non-zero exit or re-parse problems become warnings; they do **not** undo the move or make the result fail. Ruff may change formatting and imports beyond the moved blocks. Consequently the package does not guarantee exact formatting or semantic preservation, and `MovePlan` text can differ from the final file. Rename has no equivalent Ruff post-pass.

## Preview and extraction

Move `dry_run=True` and `check=True` do not apply source/target/caller edits or run Ruff. Plain dry-run does not enforce new-cycle rejection; `check=True` does. Neither executes tests, type checking or imports of the refactored code.

Extract needs a target file for the move pipeline. If absent, it creates the target and missing parents **before** planning, then removes that scaffold on dry-run or a raised move. Thus preview requires write permission and has temporary filesystem effects. Scaffold creation itself is outside the cleanup try/finally, so failure while creating it may leave directories. A successful no-op extract can retain an empty scaffold. Cleanup errors and concurrent writers are not a transactional guarantee.

## Static rewriting has boundaries

- Move repairs recognized `from module import Name` and module-attribute caller patterns inside the scanned root. Dynamic imports, string-based lookups, external repositories and unsupported import forms require manual review.
- Rename discovers `from module import Name` callers and applies name rewriting throughout those modules. It is not a complete lexical symbol resolver: shadowing, aliases, unrelated same-named identifiers, star imports and re-export chains can escape or be over-rewritten. Bare `import module; module.Name` callers are not discovered by rename's caller pass.
- In-flight renaming rewrites supported references and string annotations in moved blocks; this does not mean arbitrary strings throughout the workspace are repaired. Source forward-reference warnings identify remaining names requiring manual edits.
- `include_helpers=False` intentionally leaves referenced helpers/constants unresolved unless the destination already provides them. The warning is not a compatibility check.
- Copying shared helpers duplicates implementation. `shared_helpers="error"` can force an explicit ownership decision. The shared-helper extraction strategy is unimplemented.
- Existing literal `__all__` lists/tuples are synchronized for exported moved names; no export declaration is synthesized. Check re-export visibility and dynamic export lists manually.
- Conditional import guards can be copied whole, including their import-time behavior. Unresolvable relative imports may be dropped; inspect warnings and actual imports.
- Decorator side effects and pytest fixture-scope breaks are warnings, not blockers. Code parsing does not prove that a moved test still collects or that an application registry still loads it.
- Import-cycle detection models the statically resolved graph and ignores pre-existing cycles. If either package root cannot be discovered, or module-path derivation fails, it can return no cycle without checking a graph. A successful `check=True` is therefore not proof that every runtime import succeeds.

The [review workflow](../howto/review.md) turns a plan into a checked change. [Architecture](architecture.md) explains the transformations behind these limits.
