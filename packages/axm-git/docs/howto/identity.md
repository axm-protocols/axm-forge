# Select the commit author

`git_commit(profile="work", ...)` selects a configured profile once for the
entire batch. The resulting `--author="Name <email>"` changes the author
for those commits; it does not persist Git configuration or set the committer.
`git_merge` uses the same default identity resolution, without a profile
argument.

Default resolution uses the shared axm-config store:

| Namespace/key | Purpose |
|---|---|
| `git.default` | Required default identity with `name` and `email` |
| `git.profiles.<name>` | Named identity with `name` and `email` |
| `git.schedule` | `enabled` (default true), ordered `rules` |
| `echo.workspace_roots` | Roots under which schedule rules apply |

The first matching schedule rule selects its profile; outside the roots,
with scheduling disabled, or with no match, the default identity applies.
An explicit unknown profile warns and returns no selected identity rather
than falling back to the configured default: Git then uses its normal author
configuration. Inspect the success payload's `author`.

If no usable store configuration is resolved, the implementation can read
`~/axm/git-profiles.toml` with a migration warning. An explicit
`load_config(config_path=Path(...))` reads that exact TOML file; this is an
internal Python helper, not a `git_commit` parameter.

Example of an explicit file's structure (not the shared store layout):

```toml
timezone = "Europe/Paris"
workspace_paths = ["/absolute/workspaces"]

[default]
name = "Example Author"
email = "author@example.invalid"

[profiles.work]
name = "Work Author"
email = "work@example.invalid"

[schedule]
enabled = true

[[schedule.rules]]
profile = "work"
days = ["mon", "tue", "wed", "thu", "fri"]
start = "09:00"
end = "18:00"
```

The model supports timezone-aware scheduling (default `Europe/Paris`).
The current shared-store loader does not read a `git.timezone` scalar into
that model, so the default timezone applies on that path; an explicit file
can supply `timezone`. Invalid stored/file configuration is logged and may
resolve to no identity. An unsafe axm-config home error propagates.

These helpers and their models are documented in the
[generated identity API](../reference/axm_git/core/identity.md); they are not
re-exported from the package root.
