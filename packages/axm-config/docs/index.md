# axm-config

Configure non-sensitive AXM runtime settings with `env > active-profile file > default`.
The library provides generic resolution, Pydantic model binding, typed runtime
accessors and execution-policy storage. It also distributes an `axm-config`
console script and two AXMTools.

## Learn

[Getting started](tutorials/getting-started.md) installs the package and follows a
non-sensitive setting from persistence through an environment override to removal.

## Accomplish a task

- [Load a consumer configuration](howto/load-a-consumer-config.md).
- [Select a profile and understand isolation](howto/profiles.md).
- [Set or remove a ticket execution policy](howto/execution-policies.md).

## Look up a contract

- [CLI and AXMTools](reference/cli.md): commands, output and failures.
- [Resolution and public Python contracts](reference/contracts.md): names, types,
  exceptions and low-level store operations.
- [Runtime settings](reference/runtime-settings.md): keys, defaults and validation.
- [Python API](reference/api.md): rendered signatures for the public exports and tools.

## Understand persistence

[Architecture and persistence](explanation/architecture.md) explains migration,
atomic replacement, concurrency limits and the boundary with axm-vault.

The production store is `~/.axm/config.toml`; a named profile uses
`~/.axm/profiles/<name>/config.toml`. Values are plaintext: never use the store
for API keys, tokens or passwords. `AXM_HOME` does not relocate this store.

The repository README is a short introduction; this page is the site entry point.
