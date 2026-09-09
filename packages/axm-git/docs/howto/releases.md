# Inspect and publish a release

## Read-only analysis

Call `git_release_diff` with the **package directory**:

```json
{
  "name": "git_release_diff",
  "arguments": {"path": "/absolute/repository/packages/axm-git"}
}
```

This façade request reads local tags and history; it does not fetch or publish.
The tool obtains the tag prefix from the package's
`[tool.hatch.version].tag-pattern`. For axm-git this yields `axm-git/`.
The latest matching local tag is selected by Git version sorting, not by
proving it is an ancestor of HEAD.

The result includes `current_tag`, `suggested_bump`, `suggested_next`,
`breaking`, `commits_since`, `counts`, `files_changed`, `diffstat` and
`public_api_touched`. Commit records contain `hash`, `type`, `breaking`
and `subject`; count keys are dynamic.

## Limits of the suggestion

History is scoped to the package, but public-API detection only checks whether
a changed path matches `src/**/__init__.py`. It is not a signature/compatibility
analysis. The tools use commit subjects; a breaking-change footer appearing
only in the commit body is not available to their classifier.

Before 1.0, a breaking change or feature produces a minor bump; other changes
produce a patch. At/after 1.0, a breaking change produces a major bump.
Only plain three-component versions are supported, without prerelease suffixes.

Without a previous tag, release-diff suggests `0.1.0`; its diff uses
`git diff HEAD`, which describes working-tree changes rather than all first
release contents. It may suggest a bump even when its commit list is empty.
Review the evidence instead of treating a suggestion as a publish gate.

## Publish a tag

**The following call creates an annotated local tag and pushes it to origin.**
Use it only after deciding to publish; it has no preview, list, dry-run,
custom-remote or local-only parameter.

```json
{
  "name": "git_tag",
  "arguments": {
    "path": "/absolute/repository/packages/axm-git",
    "version": "v1.2.3"
  }
}
```

The version shown is illustrative; choose a version greater than the current
matching tag. Omit `version` for automatic selection. Pass the bare version
(`1.2.3` or `v1.2.3`), not `axm-git/v1.2.3`; the prefix is added by the tool.

The operation checks repository existence and a clean tree, obtains CI state,
requires commits since the previous tag, computes/validates the version,
creates the tag, attempts hatch-vcs verification, then pushes.
The hatch-vcs check is best effort; a null `resolved_version` does not block push.

**The CI check blocks only `red`.** It queries at most three recent runs on
the resolved default branch and matches HEAD. `pending`, `error` and
`skipped` do not block publication. Missing gh, an empty run list or a failed
gh query can yield `skipped`. A matching run does not establish that all
required workflows passed. Check your required CI independently.

Automatic tagging reads repository-wide commit subjects since the matching
tag, unlike package-scoped release-diff. The suggested versions can therefore
differ. Without a prior tag, tagging computes from `v0.0.0`, so a patch-only
first release can become `v0.0.1` instead of release-diff's `0.1.0`.
Use an explicit reviewed version for a package release when these scopes differ.

## Partial failure and downstream publication

On successful push, `tag` is the bare version with `v`; `full_tag` includes
the package prefix. Other keys are `bump`, `breaking`, `resolved_version`,
`pushed`, `ci_check`, `commits_included` and `current_tag` (`"none"` if absent).

If the push fails, `success=False` and `pushed=False`, but the local tag
remains. A timeout may also occur after a local mutation. Inspect local and
remote state before retrying: repeating tag creation will not repair an
existing local tag automatically.

A pushed tag may trigger repository CI, releases or package publishing.
The tool neither waits for those workflows nor creates a GitHub Release
directly. Tag push success does not prove a package was published.
