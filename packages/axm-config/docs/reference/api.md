# Python API

The root surface is the public import contract. The narrative
[contracts](contracts.md), [runtime defaults](runtime-settings.md) and
[profile limits](../howto/profiles.md) take precedence over overbroad legacy
docstrings about atomicity, read-only behavior or isolation.

::: axm_config
    options:
      members: true
      inherited_members: false
      show_root_heading: true
      show_source: false

## Registered provenance tool

This class is registered under `axm.tools` but is not exported by the root.

::: axm_config.tools.ConfigDoctorTool
    options:
      show_root_heading: true
      show_source: false

## Documentation build

This static directive page is built both standalone and in the workspace nav.
The workspace generator additionally emits module pages under
`reference/axm_config/`; it does not generate this package's former
`reference/api/` target. This page needs only the Python mkdocstrings handler
and the configured local source path, without relying on that generator.
