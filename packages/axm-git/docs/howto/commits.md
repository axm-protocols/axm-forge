# Commit explicit files and handle hooks

A commit changes local history and the index. It does not push.
Prepare the exact file list from a repository-wide preflight and inspect any
already staged paths before starting.

## Stage and commit

Python example for a repository containing the named changes:

```python
from axm_git.tools.commit import GitCommitTool

result = GitCommitTool().execute(
    path="/absolute/repository",
    commits=[
        {"files": ["src/example.py"], "message": "fix: correct example"},
        {"files": ["obsolete.txt"], "message": "chore: remove obsolete file"},
    ],
    strict=True,
)
if not result.success:
    print(result.error)
    print(result.data)
else:
    print(result.data["results"])
    print(result.data["hook_autofixed_files"])
```

The second spec assumes `obsolete.txt` was tracked and has already been
deleted. Deletions are staged automatically; a never-tracked missing path
fails. Gitignored paths are skipped. Files resolve against the repository
root first, then the supplied working directory. Prefer repository-relative
paths to avoid ambiguity when both locations contain the same name.

Each spec needs a non-empty `message` and `files`; optional `body` adds
another commit-message paragraph. `strict=True` rejects a non-Conventional
Commit message; the default merely warns.

The tool stages paths itself. It refuses staged paths outside the declared
spec, with an exemption for autofixed paths accumulated earlier in the batch.
For a package-directory call, the index check accepts both root-relative and
package-relative candidates for a declared name. This can admit an extra
staged path when the same name exists in both places; prefer a repository-root
call with unambiguous file paths.

The batch is **sequential, not transactional**: earlier commits remain if a
later spec fails. Review `results` and `succeeded`; resume only the outstanding
work after checking current Git state.

## Commit-hook retry

Git runs the repository's commit hooks. A failed commit whose combined output
contains `files were modified` causes one re-stage of the declared files and
one retry. Arbitrary hook failures do not all trigger a retry.

On full success, `hook_autofixed_files` is a sorted, deduplicated list and
`author` is the selected author or null. `results` entries contain short
`sha`, `message`, `precommit_passed` and `retried`.

The autofix list is captured with a repository-wide `git diff --name-only`
before re-staging. It can include pre-existing unstaged changes and does not
prove that every listed file was changed by a hook or committed. An empty list
does not establish byte-for-byte patch equality. Review the actual diff when
the distinction matters.

## Recover from refusal

A definitive hook refusal or unexpected-index rejection can return:

- `results`, `total`, `succeeded`: completed work and batch progress.
- `unexpected_staged`: unrelated staged paths for an index rejection.
- `failed_commit`: `index` (one-based), `message`, `precommit_output`,
  `auto_fixed_files`, `retried`, `index_restored`, `restored_paths`.

Do not assume these keys exist on validation errors or timeouts.
The top-level success key `hook_autofixed_files` is not present on every
failure. Check for `failed_commit` before accessing it.

On the definitive refusal paths, the tool unstages the paths it added to the
index delta. This is not a byte-for-byte snapshot restore of partially staged
files, and it does not undo working-tree edits made by hooks. A staging error
can also leave earlier staging work in place. Re-run preflight and inspect
the index before retrying; do not replay successful commits.

For author selection, see [identity](identity.md).


## Declare a dependency runtime

`GitCommitTool.DEPENDENCY_ENVIRONMENT_VERSION == 1` is the public capability
for consumers that require an explicit runtime. Check it before calling an
older backend: old tools accepted arbitrary keyword arguments and could
silently ignore this contract. Upgrade Forge before enabling the caller.

```python
from axm.tools.dependency_reads import DependencyEnvironment
from axm_git.tools.commit import GitCommitTool

assert GitCommitTool.DEPENDENCY_ENVIRONMENT_VERSION == 1
result = GitCommitTool().execute(
    path="/absolute/candidate",
    commits=[{"files": ["packages/example/src/example.py"], "message": "fix: example"}],
    dependency_environment=DependencyEnvironment(
        interpreter="/absolute/read-only-venv/bin/python",
        package_root="/absolute/candidate/packages/example",
        pythonpath=("/absolute/declared/dependency/src",),
    ),
)
```

The same parameter accepts a JSON mapping with `interpreter`, `package_root`
and optional `pythonpath` list. Locations must be absolute, the interpreter
must be an existing executable, and `package_root` must belong to the candidate.
Invalid contracts return `dependency_environment.status="invalid"` before
staging. They are input errors, not automatically instrument failures.

The interpreter path remains lexical: symlink resolution must not erase its
virtual-environment identity. Its directory precedes the inherited `PATH`.
The candidate package's `src`, package root and sibling `packages/*/src`
precede the explicitly declared dependency paths in `PYTHONPATH`; the
service's ambient `PYTHONPATH` is not added. Hooks can consume
`AXM_DEPENDENCY_INTERPRETER` and `AXM_DEPENDENCY_PACKAGE_ROOT` directly.
Bytecode writes are disabled. No venv is created or prepared by this transport.

Each invocation uses an immutable scoped snapshot and each subprocess gets
its own copy, including root discovery, staging, restoration and autofix
retries. Nested scopes and exceptions restore the previous context; concurrent
invocations remain independent. `os.environ` is never modified. Without an
explicit dependency environment, the existing behavior is preserved.

`run_git(env=...)` accepts a complete subprocess environment outside such a
scope. Inside it, supplied Git-local options such as `GIT_INDEX_FILE` overlay
the scoped snapshot, while declared Python runtime keys remain authoritative.
Neither caller mapping is mutated.

This feature transports the environment and preserves the repository's hooks,
selection, filters, stages, arguments, autofix and commit-message veto. It does
**not** certify arbitrary hooks as free of bootstrap, prevent their manager
from creating environments, or change their commands. In particular, the Hub
configuration's remote prek hooks and `uv --isolated` are not validated by this
change. Their activation remains blocked operationally until an independent
public readiness/no-prepare provider or proven confinement is available.
Passing environment variables alone cannot supply that guarantee.

### Commit timeouts

A timeout during the first commit attempt or the single autofix retry stops the
batch. No additional commit attempt is made. The tool resets only the staging
delta introduced by this invocation; entries staged before it remain staged.
The refusal includes `failed_commit.cause = "timeout"`, `timeout_seconds`,
`index_restored`, `restored_paths`, retry/autofix metadata, and the captured
stdout/stderr in `precommit_output` (at most 8192 characters per stream).

The default timeout is 30 seconds **per Git subprocess**, not a deadline for the
whole batch. A commit may have one autofix retry; staging, probes and restoration
have their own subprocess timeouts. This mechanism does not certify termination
of every descendant of a hook or establish hook-environment readiness.

If the scoped reset is refused or times out, the original cause remains intact,
`index_restored` is false, `restored_paths` is empty and `restore_error` records
the restoration failure (bounded to 8192 characters). No restoration is claimed
without a successful Git reset.
