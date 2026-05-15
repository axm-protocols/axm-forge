# Extending tuple-naming to `tests/e2e/`

Companion to `README.md`. The current prototype handles `tests/integration/`
only. This document captures the design for extending it to `tests/e2e/`
without breaking the conceptual model already in place.

## Context — how AXM classifies e2e

`axm_audit.core.rules.test_quality.pyramid_level.classify_level` resolves
the level deterministically from soft signals:

```
if has_subprocess:                            → e2e
elif not has_real_io and imports_public ...   → unit (rescue)
elif has_real_io:                             → integration
elif imports_internal:                        → unit
else:                                         → unit
```

So in the AXM model, **e2e is, by construction, "test that calls a
subprocess or a CLI runner."** There is no e2e-by-HTTP, no e2e-by-MCP-
transport, no e2e-by-SDK in this taxonomy — those would all show up as
integration (real I/O without subprocess) or unit (pure functions).

That simplifies the e2e naming problem considerably: every e2e test
contains at least one `subprocess.*([...])` call or a
`CliRunner().invoke(app, [...])` call, and the tokens of that call are
extractable from the AST.

## Canonical e2e filename

Apply the **same rule** as for integration — top-K=2 by usage frequency,
sorted alphabetically, dash-separated, snake_case — but the "symbol"
counted is no longer a Python identifier, it is a **CLI invocation
key**.

The invocation key of a `subprocess.run([...])` call (or any equivalent)
is the **tuple of positional tokens before the first flag**, capped at
two levels of nesting:

| Call site                                                  | Invocation key            | Filename                          |
|------------------------------------------------------------|---------------------------|-----------------------------------|
| `subprocess.run(["axm-audit", "--help"])`                  | `(axm-audit,)`            | `test_axm_audit.py`               |
| `subprocess.run(["axm-audit", "audit", "--json"])`         | `(axm-audit, audit)`      | `test_axm_audit-audit.py`         |
| `subprocess.run(["axm-audit", "audit", "category", "x"])`  | `(axm-audit, audit)` (capped) | `test_axm_audit-audit.py`     |
| `CliRunner().invoke(app, ["check", str(tmp_path)])`        | `(<bin>, check)`          | `test_<bin>-check.py`             |
| `subprocess.run([str(BIN), "init", "--name", "x"])`        | `(<bin>, init)`           | `test_<bin>-init.py`              |

Where `<bin>` is the name of the binary the package declares in
`[project.scripts]` of its `pyproject.toml` (for `CliRunner`, the `app`
object is mapped back to its declared script name).

This is intentionally symmetric with the integration convention:

| Tier        | Counted unit              | Source                          |
|-------------|---------------------------|----------------------------------|
| integration | Python symbol             | `from pkg import X` + closure   |
| **e2e**     | **CLI invocation key**    | `subprocess.run([...])` literal |

Both flow into the same `test_<a>-<b>.py` filename pattern, both use
K=2, both sort their tuple alphabetically.

## What counts and what does not

A single e2e test can perform multiple subprocess calls. The proto
currently treats them all equally for symbol counting; for e2e they
must be filtered, otherwise setup commands swamp the SUT call:

```python
def test_check_on_scaffolded_project(tmp_path):
    # SETUP — not the SUT
    subprocess.run(["git", "init", str(tmp_path)], check=True)
    subprocess.run(["uv", "venv"], cwd=tmp_path, check=True)

    # SUT — what this test actually verifies
    result = subprocess.run(["axm-init", "check"], cwd=tmp_path)
    assert result.returncode == 0
```

The naive tuple would be `(axm-init, git, uv)` — meaningless. The fix
is a **deterministic filter**:

> An invocation counts toward the tuple **iff** `argv[0]` appears in the
> `[project.scripts]` table of the package under test's `pyproject.toml`.

Anything else (`git`, `uv`, `pytest`, `pip`, …) is treated as setup
plumbing and ignored, exactly as one ignores stdlib imports when
collecting integration symbols. The filter is the e2e analogue of
"only imports from `PACKAGE` count" used for integration.

If no in-package invocation is found in the test, the file is
**UNKNOWN** at the e2e tier — same semantics as a no-package-symbol
integration test, same recommendation (likely a misclassified test or
a test of an external utility wearing a package coat).

## Tokens extracted from the AST

`subprocess.run` and friends accept several call shapes. The extractor
must handle each deterministically:

| Pattern                                              | argv recovery                                |
|------------------------------------------------------|----------------------------------------------|
| `subprocess.run(["bin", "sub"])`                     | list literal — take string elements          |
| `subprocess.run(["bin", "sub", *args])`              | list literal — only literal elements counted |
| `subprocess.run([BIN, "sub"])` with `BIN = "bin"`    | resolve module-level string constants        |
| `subprocess.run(f"{bin} sub", shell=True)`           | skip (shell=True is non-deterministic)       |
| `subprocess.run(cmd)` with `cmd = [...]`             | trace one level of intra-function binding    |
| `CliRunner().invoke(app, ["sub"])`                   | resolve `app` to declared script via         |
|                                                      | `[project.entry-points]`                     |
| `runner.invoke(app, ["sub"])`                        | same                                         |

The extractor lives next to the integration symbol extractor and shares
its philosophy: **trace what is statically resolvable, skip the rest,
report skips as a known limit rather than guess.** A test whose argv
is dynamically built (concatenation, `*args` unpacking, format strings)
falls through and the file is reported as a low-confidence detection,
not silently mis-attributed.

## Calling order, multiple invocations, and K=2

When a test invokes the package binary several times with different
subcommands (e.g. an end-to-end "init then check" scenario), the test
contributes the tuple of its top-K=2 most-frequent `(bin, sub)` pairs,
identically to how an integration test contributes its top-K=2 Python
symbols. If "init" and "check" each appear once, the canonical file
becomes `test_<bin>-check-init.py` (sorted) — i.e. the file groups
the two-step scenario as one logical e2e under both endpoints.

This is desirable: e2e scenarios that exercise N commands at once are
exactly the cases where the file belongs in the intersection of those
commands' test surfaces, not under either one alone.

If a test invokes more than two distinct in-package commands, the
top-2 by usage win — same coalescence policy as integration.

## What the `TEST_QUALITY_NO_PACKAGE_SYMBOL` rule looks like, extended

The proposed rule (see `README.md`) becomes a **two-criterion**
predicate when the test lives in `tests/e2e/`:

A test exercises its package iff **either**:

- (integration-style) it references at least one first-party symbol
  through imports + intra-module closure + fixture resolution, **OR**
- (e2e-style) it issues at least one subprocess / CLI-runner invocation
  whose `argv[0]` is in the package's `[project.scripts]`.

If **neither** holds, the test is UNKNOWN — flagged for review with the
same `WARNING` severity and the same fix-hint family ("express the
invariant as a versioned rule of the target package, or move it to a
linter outside the pytest suite").

The two criteria are independent: a unit test under `tests/unit/` is
exempt (the rule only runs on integration/e2e). A test in
`tests/integration/` that for some reason calls the package binary
also passes (legitimate cross-tier overlap).

## Implementation notes (for the port to a real rule)

The proto already has `_collect_package_imports`, `_used_names_in_node`,
`_closure_nodes_for_test`, `_collect_fixtures`,
`_resolve_fixture_symbol` — these all carry over verbatim. The new
work is:

1. **`_collect_project_scripts(project_path)`** — parse
   `pyproject.toml`, return the set of script names declared under
   `[project.scripts]` and the `app` objects declared under
   `[project.entry-points."console_scripts"]` (if both styles are in
   use). Cache once per project.

2. **`_extract_subprocess_invocations(tree, scripts)`** — walk the AST
   for the call patterns above, return the list of `(bin, sub)` tuples
   whose `bin` is in `scripts`. Skip dynamic-argv cases without raising.

3. **`_extract_cli_runner_invocations(tree, app_to_script)`** — same
   but for `CliRunner().invoke(...)` / `runner.invoke(...)`. Map the
   `app` object to its script name via the imports collected in step 1.

4. **Per-test invocation closure** — same trick as the integration
   closure: a test method that calls a module-level helper which
   issues `subprocess.run(...)` should attribute that invocation back
   to the test, not silently lose it. Reuse the existing
   `_closure_nodes_for_test` and walk subprocess patterns inside each
   closure node.

5. **File-level union and cohesion** — identical to the integration
   path, no change needed.

6. **Filename emission** — same `to_snake` + dash join. Script names
   often contain `-` already (`axm-audit`, `axm-init`); convert to
   `axm_audit` for filename-safety, then re-join with `-` as separator
   so `(axm-audit, audit)` emits `test_axm_audit-audit.py`. The
   `-`-vs-`_` collision inside binary names is the only edge case
   worth a comment in the implementation.

## Open questions for the next session

- **Multi-binary packages.** Some packages declare more than one script
  (e.g. `axm-audit` ships `axm-audit` and `axm-audit-completion`).
  Should the binary part of the tuple still be required when there is
  only one script in the package? Probably not — singleton scripts
  could collapse to `test_<sub>.py` to match the singleton-symbol
  case in integration. To decide once we have data.

- **MCP servers as e2e.** `axm-mcp` ships an MCP server, not a CLI.
  Tests against it go through an MCP client, not subprocess. Under
  the strict AXM taxonomy they are integration (real I/O, no
  subprocess), so the e2e folder of `axm-mcp` may legitimately stay
  empty — or AXM may want to extend `has_subprocess` to include
  "spawns an MCP server process." Out of scope for the first port;
  worth raising explicitly.

- **`subprocess` calls inside fixtures.** A fixture that scaffolds a
  project with `subprocess.run(["axm-init", "scaffold", ...])` and is
  consumed by many tests effectively transfers the e2e signal to all
  of them. The proto's fixture resolver already chases this for
  symbol-typed fixtures; the subprocess-typed fixture case should
  reuse the same machinery.
