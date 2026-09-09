# Python API

Root exports below are the package's public import surface. The narrative
[architecture](../../explanation/architecture.md) documents behavior and limitations;
some source docstrings still use broader “never-leak” wording. API tables here
show contracts without repeating those descriptions.

::: axm_vault
    options:
      members: true
      show_root_heading: true
      show_docstring_description: false
      show_docstring_examples: false
      show_source: false

## Resolver singleton

The root export `resolver` is a preconstructed, non-interactive `Resolver()`.
Use its `resolve` and `probe` methods as described in [Resolver](../resolver.md).
It is a runtime instance, rather than another class or factory.

## Module-level surfaces

The installed tools include `VaultDeleteTool`, although it is not a root export.
`KeyringUnavailableError` and `groups_from_provider` likewise require their
module paths. They are listed separately rather than implied root imports.

::: axm_vault.tools.VaultDeleteTool
    options:
      show_docstring_description: false
      show_source: false

::: axm_vault.store.KeyringUnavailableError
    options:
      show_docstring_description: false
      show_source: false

::: axm_vault.catalog.groups_from_provider
    options:
      show_docstring_description: false
      show_source: false
