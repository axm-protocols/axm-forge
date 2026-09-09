# Bootstrap a machine

## Review first

```bash
axm-doctor check
```

Inspect [install plans](../reference/python.md#installation) and the missing
credential groups before applying changes. The built-in install registry
covers uv, Claude Code and Codex. Other absent binaries are reported without
a guessed install command.

## Apply interactively

The following command can install tools and delegate credential writes:

```bash
axm-doctor bootstrap
```

For absent tools with a known plan, the CLI prints the command and asks
`[y/N]`; `y` or `yes` confirms (case-insensitive). It then offers one
confirmation for vault setup of the missing groups. Vault may prompt further.

Install success requires both a zero return code and a present post-check.
A failed installation is printed, but does not itself force a nonzero
bootstrap exit. Exceptions caught by the CLI do exit 1. Re-run diagnostics
and inspect outcomes after bootstrap; its exit 0 is not a health verdict.

## Non-interactive use

Without a TTY, the tool-install loop skips entirely.
The secrets half still discovers missing credentials and can print/read its
confirmation prompt. Closed stdin is treated as a decline; piped text can be
read. Even if confirmed through that prompt, `provision_missing(confirm=True)`
refuses vault setup without a TTY and returns a reason.

Do not use bootstrap as an unattended provisioning engine. Use the read-only
tools for automation and leave application to a separately controlled step.

## Partial outcomes and accounts

`provision_missing()` returns group names without writing. Confirmed execution
calls vault's `run_setup(only=group)` once per group, then scans again.
A skipped prompt or unresolved spec makes `provisioned=False`. An aborted
setup returns early; earlier groups may already have changed, without rollback.

The structured missing rows identify accounts, but the current CLI secret
labels, `setup_hint`, and `still_missing` strings omit the account.
Use the structured rows to disambiguate and consult vault's account-aware
setup interface before applying a hint to a multi-instance group.

## Extend installation support

There is no public install-registry registration API. Adding a built-in tool
requires a package change to its internal registry and verification of the
execution and post-check paths. Applications can construct a public
`InstallPlan`, but must validate their own command and URL: the executor is
not an allowlist of known registry plans.
