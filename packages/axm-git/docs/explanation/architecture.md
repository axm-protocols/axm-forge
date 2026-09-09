# Architecture and guarantees

## One tool implementation, several interfaces

The classes in `axm_git.tools` inherit `AXMTool` and expose keyword-only
`execute` methods returning `ToolResult`. The `axm.tools` entry points
register them for the generic CLI, MCP and tool-node consumers.
The tools spawn Git and gh subprocesses through shared runner helpers.

Git operations are not all transactional or idempotent. A failed batch can
leave earlier commits; a failed tag push leaves the local tag; a failed
squash commit can leave staged changes. The caller must inspect partial
results and repository state. See [commit recovery](../howto/commits.md),
[merges](../howto/collaboration.md) and [releases](../howto/releases.md).

## Package boundaries

`axm_git.__init__` exports only `__version__` and `__version_tuple__`.
The supported tool entry points are listed in the
[tool reference](../reference/cli.md); direct Python calls import the concrete
tool module. Generated reference pages also describe internal helpers and
models, which are not a promise of root-level public exports.

Core modules provide staging/path resolution, identity selection,
Conventional Commit parsing, SemVer calculation and PR recovery.
`get_phase_commit` is an internal log-search helper; it does not supply a
protocol runtime. The package registers no lifecycle hook actions.
Git's own commit hooks are distinct and still execute during commits.

## Authentication declaration

The `axm.credentials` entry point `gh` points to
`axm_git.credentials:gh_credentials`. This callable produces a credential
group with a `GhAuthDependency`, declaring `gh auth status` as its probe and
`gh auth login` as recovery. It does not read tokens or session files.

Observable states `logged_in`, `logged_out` and `not_installed` map to the
vault states connected, disconnected and tool absent.
`GH_AUTH_CREDENTIAL` is an alias of the provider. The declaration does not
automatically authenticate or prove permission to mutate a particular repo.

## Guarantees and their limits

| Mechanism | Present behavior |
|---|---|
| Explicit staging | Declared paths, with unrelated-index rejection; no full index snapshot transaction |
| Hook retry | One retry for the recognized marker; repository-wide unstaged paths are observational evidence |
| Identity | Author argument per call, with schedule/profile resolution; no persistent Git config change |
| Push guard | Clean tree, attached branch; optional lease based on local tracking state |
| Release guard | Clean tree and non-empty history; only a red CI verdict blocks tagging |
| Subprocess timeout | Most commands bounded by runner defaults; clone explicitly disables its timeout |
| Output | Structured data for Python callers; compact display text is a separate envelope field |

The [API reference](../reference/axm_git/index.md) is rendered from source by
mkdocstrings during builds. Explicit Markdown entry pages keep these links
stable in both package and monorepo builds. The root monorepo additionally
generates a workspace-wide module reference. API bodies remain generated,
not copied signatures; verify the rendered HTML when changing configuration.
