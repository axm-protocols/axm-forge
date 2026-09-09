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
