# axm-audit — Node/Svelte Rule Intent Mapping

> **Goal**: inventory every `axm-audit` quality rule (package `packages/axm-audit`,
> 31 registered `ProjectRule` subclasses across 11 categories) and propose, for each,
> its **intent equivalent** for a Node/Svelte project (TypeScript + SvelteKit), using
> the standard tooling of that ecosystem.
>
> **No new tools, no architecture change.** The mechanism stays
> `@register_rule(category)` → `_RULE_REGISTRY[category]` → `get_rules_for_category`.
> We only add a `framework` axis (default `"python"`; new values `"node"` and
> `"svelte"`, where `svelte` inherits `node`). The proposal is to extend the decorator
> to `@register_rule(category, framework=...)`, registering parallel rule classes that
> implement the same INTENT against Node/Svelte tooling, keyed by framework.

## How the registry resolves rules (today)

`@register_rule("lint")` sets `cls._registered_category` and appends `cls` to
`_RULE_REGISTRY["lint"]`. `get_rules_for_category(category)` reads
`registry.get(category, [])` and calls `cls.get_instances()` on each. Scoring weights
live in `_CATEGORY_WEIGHTS` (lint/type/complexity 0.15; security/deps/testing/
test_quality/architecture 0.10; practices 0.05); `structure` + `tooling` are
non-scored. The framework axis would simply partition each category bucket by
framework (resolve = `registry[category][framework]`, with `svelte` falling back to
`node`), leaving categories, weights, scoring, `CheckResult` and the auditor loop
untouched.

## Inventory + mapping table

| rule_id | catégorie | intention (1 phrase) | outil Python | équivalent Node/Svelte (outil) | parité | notes de portage |
|---|---|---|---|---|---|---|
| `QUALITY_LINT` | lint | Style/correctness lint, score = 100 − issues×2 | `ruff check --output-format=json` | `eslint --format json` (typescript-eslint, `eslint-plugin-svelte`) | 1:1 | ESLint emits JSON `[{filePath,messages:[{ruleId,line,message}]}]`; flatten to same `{file,line,code,message}`. Svelte adds `eslint-plugin-svelte` + `svelte-eslint-parser`. |
| `QUALITY_FORMAT` | lint | Code is formatted, score = 100 − unformatted×5 | `ruff format --check` | `prettier --check` (+ `prettier-plugin-svelte`) | 1:1 | `prettier --check` exits non-zero and lists unformatted paths on stdout; same parse as `_parse_unformatted_files`. |
| `QUALITY_TYPE` | type | Zero type errors (any error = fail), score = 100 − errors×5 | `mypy --output json` | `tsc --noEmit` + `svelte-check` (`.svelte`) | adapté | `tsc --noEmit` has no native JSON; parse `--pretty false` line format `file(line,col): error TSxxxx: msg`, or use `tsc -p tsconfig.json --noEmit`. `.svelte` types need `svelte-check --output machine`/`--threshold error`. Two binaries → merge counts (like `parse_mypy_errors` merges lines). |
| `QUALITY_COMPLEXITY` | complexity | Flag CC≥11 OR cognitive>15 (double constraint), score = 100 − offenders×10 | radon (CC) + complexipy (Cog) | ESLint `complexity` (CC) + `eslint-plugin-sonarjs` `cognitive-complexity` (Cog) | 1:1 | Both ship as ESLint rules → one ESLint run with these two rules at `error` reproduces the exact double-constraint intent. Read counts from ESLint JSON `messages` filtered by `ruleId`. SonarJS `cognitive-complexity` threshold = 15 matches SonarSource. |
| `QUALITY_SECURITY` | security | Static security scan (high×15 + medium×5 penalty) | bandit (`--format json`) | `eslint-plugin-security` (+ severity from rule set) | adapté | No exact bandit analog; `eslint-plugin-security` (detect-eval, child_process, non-literal-fs-path, etc.) is the closest static-SAST. Map plugin findings to high/medium by rule. Could also fold `semgrep` (JS rulesets) if available. Severity buckets are coarser than bandit's. |
| `PRACTICE_SECURITY` | security | Hardcoded-secret regex scan (high-value formats + filtered keywords), score = 100 − matches×25 | in-house `re` patterns | **same regex engine, reused as-is** (scan `.ts/.js/.svelte`) | 1:1 (réutilisable tel quel) | The pattern list (`ghp_`, AWS keys, `token=`, `password=`…) is language-agnostic. Just widen the file glob from `*.py` to source extensions; the high-value-span + placeholder-filter logic is unchanged. |
| `DEPS_AUDIT` | deps | Scan deps for known CVEs, score = 100 − vulns×15 | pip-audit (`--format json`) | `npm audit --json` (or `pnpm audit --json` / `yarn npm audit`) | 1:1 | `npm audit --json` returns `vulnerabilities` map with severity; count actionable advisories. Exclude the equivalent of "env tools" noise (none, but dedupe transitive). Choose binary by detected lockfile (package-lock / pnpm-lock / yarn.lock). |
| `DEPS_HYGIENE` | deps | No unused/missing/transitive deps + pinned deps, score = 100 − issues×10 | deptry (`--json`) | `depcheck --json` (unused/missing) + `knip` (broader) | adapté | `depcheck` reports `{dependencies:[unused], missing:{}}`; `knip` is the richer modern equivalent (unused deps + exports + files). Pin check = scan `package.json` for `^`/`~`/`*` ranges on prod deps. deptry's transitive-import detection ≈ `knip`. |
| `QUALITY_COVERAGE` | testing | Run tests + enforce coverage ≥ 90%, score = coverage% | pytest + pytest-cov | `vitest run --coverage` (c8/istanbul provider) | 1:1 | Vitest emits `coverage-summary.json` (total + per-file pct) and a JSON test report (`--reporter=json`). Map total.lines.pct → score, per-file gaps → text bullets, failures → `• FAIL`. Threshold 90% configurable in `vitest.config` `coverage.thresholds`. |
| `QUALITY_DEAD_CODE` | lint | Detect unreferenced (dead) symbols, score = 100 − dead×5 | `axm-ast dead-code --json` | `knip` (unused exports/files) or `ts-prune` | adapté | `knip` is the canonical Node dead-code/unused-export detector (`knip --reporter json`); `ts-prune` is a lighter alternative. Gracefully skip if not installed (same `_skip` contract). Overlaps with DEPS_HYGIENE if knip used for both — split by reporter section. |
| `ARCH_CIRCULAR` | architecture | No circular imports (Tarjan SCC on import graph), score = 100 − cycles×20 | in-house AST import graph | `madge --circular --json` (or `dependency-cruiser`) | 1:1 | `madge --circular --json src` returns the list of cycles directly; `dependency-cruiser` has a `no-circular` rule. Svelte: madge supports `.svelte` via `--extensions svelte,ts,js` + a svelte resolver. |
| `ARCH_GOD_CLASS` | architecture | Flag oversized classes (>500 L or >15 methods), score = 100 − god×15 | in-house AST walk | ESLint `max-lines-per-function` / `max-lines` + `max-classes-per-file`; TS class-method count via AST | adapté | JS/TS favors modules over classes; intent → "oversized module/class". Closest: ESLint `max-lines` (file) + a small AST count of class methods. Svelte components: `max-lines` on `.svelte` (component bloat). Acknowledged-exempt list ports 1:1 (config table). |
| `ARCH_COUPLING` | architecture | Fan-in/fan-out coupling under threshold (orchestrator bonus + overrides), score penalised | in-house AST import metrics | `dependency-cruiser` (metrics/`forbidden` rules) or `madge` fan-out | adapté | `dependency-cruiser` computes per-module afferent/efferent coupling and supports threshold rules; `madge --json` gives the adjacency to compute fan-out in-house. Per-module override config + orchestrator bonus port 1:1 as config. |
| `ARCH_DUPLICATION` | architecture | Detect copy-pasted code (normalized AST body hashing), score = 100 − groups×10 | in-house AST hashing | `jscpd --reporters json` (token-based clone detection) | adapté | `jscpd` is the standard JS/TS copy-paste detector (supports `.ts/.svelte`), token-based rather than AST-hash but same intent; read `jscpd-report.json` clone count. `min_lines` ≈ jscpd `--min-lines`/`--min-tokens`. |
| `PRACTICE_BARE_EXCEPT` | practices | No bare `except:` (untyped catch), score = 100 − count×20 | in-house AST | ESLint `no-empty` (`catch`) + `@typescript-eslint/no-unsafe-catch`-style; ban `catch {}` / `catch (e) {}` with no use | adapté | JS has no bare-except; the intent ("don't swallow errors") maps to ESLint `no-empty: {allowEmptyCatch:false}` + `no-unused-vars` on the caught binding. One ESLint config covers it. |
| `PRACTICE_BLOCKING_IO` | practices | No blocking I/O in async (`time.sleep`), HTTP without timeout, score = 100 − count×15 | in-house AST | ESLint `no-sync` (ban `fs.*Sync` in async) + custom: fetch/axios without timeout/signal | adapté | `no-sync` bans synchronous fs/child_process calls (the Node analog of `time.sleep` in async). HTTP-timeout intent: `fetch` needs `AbortSignal.timeout`/axios `timeout` — a small custom ESLint rule or `eslint-plugin-promise`. Partial native coverage. |
| `PRACTICE_DOCSTRING` | practices | ≥80% public functions documented (abstract/override exempt) | in-house AST | `eslint-plugin-jsdoc` `require-jsdoc` (+ TSDoc) on exported symbols | adapté | `eslint-plugin-jsdoc require-jsdoc` enforces JSDoc/TSDoc on exported functions/classes; coverage % = documented/total from ESLint message count vs total exports. The abstract-stub / setter / abstract-override exemptions map to ESLint options (`exemptEmptyFunctions`, contexts). |
| `PRACTICE_TEST_MIRROR` | practices | Bidirectional 1:1 src↔unit-test mapping (missing + orphan), score = 100 − violations×15 | in-house path mapping | in-house path mapping over `src/` ↔ `tests/unit/` (`*.test.ts`) | 1:1 (réutilisable, glob adapté) | Pure filesystem logic — no external tool. Port the path algorithm: `src/x/foo.ts` ⇄ `tests/unit/x/foo.test.ts` (or co-located `foo.test.ts`). Svelte: `Button.svelte` ⇄ `Button.test.ts`. Exempt config + underscore-stripping concept → drop the `_` notion (use `.private`/barrel exempt). |
| `PRACTICE_TEST_SCENARIO_NAMING` | practices | Integration/e2e tests must NOT be named after source modules (anti-mirror), score = 100 − violations×15 | in-house path mapping | in-house path mapping over `tests/integration` + `tests/e2e` | 1:1 | Filesystem-only; reuse the algorithm against the Node test layout. Same exempt-paths config. |
| `STRUCTURE_TESTS_PYRAMID` | structure | 3-level pyramid dirs exist + pytest markers declared | in-house + pyproject markers | in-house: `tests/{unit,integration,e2e}` exist + vitest workspace projects/tags declared | adapté | Vitest has no pytest markers; the "markers declared" half maps to `vitest.workspace.ts` projects or `test.include` globs per level (or Playwright project for e2e). Dir-existence half is 1:1. |
| `STRUCTURE_PYPROJECT` | structure | PEP 621 metadata completeness (9 fields), score = present/9×100 | tomllib parse of pyproject.toml | parse `package.json` field completeness (name, version, description, type, license, author, repository, exports/main, engines) | adapté | Direct field-presence analog on `package.json` (JSON, no toml). Choose the 9 canonical npm fields. Svelte adds `svelte.config.js`/`vite.config.ts`/`tsconfig.json` existence (see new Svelte-specific rows). |
| `TEST_QUALITY_DUPLICATE_TESTS` | test_quality | Cluster likely-duplicate test functions (structural signals), score = 100 − pairs×penalty | in-house AST clustering | in-house AST clustering over `*.test.ts`/`*.spec.ts` (ts-morph / TS compiler API) | adapté | Reimplement the structural clustering on the TS AST (via `ts-morph` or the TS compiler API). `vitest`'s `it`/`test`/`describe` are the test-func boundary. Heavy port (no off-the-shelf tool) but the intent + acknowledged-config carry over. |
| `TEST_QUALITY_FILE_NAMING` | test_quality | Integration/e2e file names match canonical top-K symbol tuple, or should be split | in-house AST + canonical-name | in-house AST canonical-name over `tests/integration` + `tests/e2e` | adapté | Reimplement canonical-tuple derivation against TS imports (the first-party symbols a test exercises). No external tool; same Finding/severity scoring. |
| `TEST_QUALITY_NO_PACKAGE_SYMBOL` | test_quality | Integration/e2e tests must exercise a first-party symbol or in-package CLI | in-house AST | in-house AST: test imports a `src/` symbol or invokes the package bin | adapté | Port the import-resolution + script-exercise check to TS imports (`import … from '$lib'`/package name) and `package.json` `bin`. Same per-file intent. |
| `TEST_QUALITY_PRIVATE_IMPORTS` | test_quality | Tests must not import private (`_prefixed`) first-party symbols | in-house AST | in-house AST: tests must not import non-exported / `internal` symbols | adapté | JS has no `_` privacy convention; the intent maps to "don't deep-import past the package's `exports` map / barrel". Flag `import { x } from 'pkg/src/internal/...'` or imports of `@internal`-tagged TSDoc symbols. Reimplement against `package.json` `exports` + barrel boundaries. |
| `TEST_QUALITY_PYRAMID_LEVEL` | test_quality | A test's classified level (by I/O signals) must match its folder | in-house AST classifier | in-house AST classifier over `*.test.ts` (detect fs/net/subprocess) | adapté | Reimplement the I/O-signal classifier on TS AST: filesystem (`fs`), network (`fetch`/`http`), subprocess (`child_process`) → integration/e2e; pure memory → unit. Same mismatch scoring. |
| `TEST_QUALITY_TAUTOLOGY` | test_quality | Detect tautological assertions (`expect(true).toBe(true)`, self-compare, mock-echo) + triage | in-house AST + triage | in-house AST over vitest assertions (`expect(...).toBe(...)`) | adapté | Port the tautology detector + triage to vitest matcher AST: `expect(x).toBe(x)`, `expect(true).toBeTruthy()`, asserting a mock's own return. Same MUSCLE/MARK/STRENGTHEN buckets; MARK = a `// tautology-ok: reason` comment instead of the pytest marker. |
| `TOOL_RUFF` / `TOOL_MYPY` / `TOOL_UV` | tooling | Required CLI tools are on PATH | `shutil.which` | `which`/`execa.command` for `eslint`, `tsc`, `prettier`, `vitest`, (`pnpm`/`npm`) | 1:1 | `ToolAvailabilityRule.get_instances()` iterates `_REQUIRED_TOOLS`; for Node the list becomes the Node toolchain (`["eslint","tsc","prettier","vitest","npm"]`, svelte adds `svelte-check`). Pure PATH check, framework-parametrized list. |
| `FILE_EXISTS_*` | structure | A required file exists (NOT auto-registered — axm-init only) | `Path.exists` | `Path.exists` on Node gold-standard files | 1:1 | Not in the audit registry (consumed by axm-init checklist). Node analog = required-file checks for `package.json`, `tsconfig.json`, `vite.config.ts`. Same `FileExistsRule` class, different filenames. |
| `DIR_EXISTS_*` | structure | A required directory exists (NOT auto-registered — axm-init only) | `Path.is_dir` | `Path.is_dir` on Node gold-standard dirs | 1:1 | Same as above; e.g. `src/`, `src/routes/` (SvelteKit), `tests/`. |
| `QUALITY_DIFF_SIZE` | lint | Warn on oversized uncommitted diff (ideal 400 / max 1200 lines) | `git diff --stat` | **same `git diff --stat`, reused as-is** | 1:1 (réutilisable tel quel) | Git-based, language-agnostic. No change needed beyond registering it under the node/svelte framework so it runs in those projects. |

### New Svelte-specific rows (no Python analog — net-new)

| rule_id (proposé) | catégorie | intention | équivalent Node/Svelte (outil) | parité | notes |
|---|---|---|---|---|---|
| `SVELTE_CHECK` | type | Svelte component type/template diagnostics (props, slots, bindings, a11y) | `svelte-check --output machine` | Svelte-spécifique | Folds into `QUALITY_TYPE` for svelte framework, or stands alone. Covers what `tsc` cannot see inside `.svelte` markup. |
| `SVELTE_A11Y` | lint | Accessibility lint of Svelte markup | `eslint-plugin-svelte` a11y rules (or compiler `a11y-*` warnings) | Svelte-spécifique | The Svelte compiler emits `a11y-*` warnings natively; surface them as a lint sub-score. |
| `STRUCTURE_SVELTEKIT_CONFIG` | structure | Required SvelteKit config files present + coherent | existence of `svelte.config.js` + `vite.config.ts` + `tsconfig.json` (extends `.svelte-kit/tsconfig.json`) | Svelte-spécifique | Extends `STRUCTURE_PYPROJECT`'s "scaffolding completeness" intent to the SvelteKit toolchain trio. |

## Synthèse

**31 registered rule classes** (+ 2 non-registered `FileExists`/`DirectoryExists`
consumed only by axm-init; `ToolAvailabilityRule` expands to 3 `TOOL_*` instances).
Counting by distinct rule_id surface, the intent-portability breakdown:

| Verdict | Count | rule_ids |
|---|---|---|
| **(a) Portable 1:1** (same intent, off-the-shelf or reusable-as-is tool) | 11 | `QUALITY_LINT`, `QUALITY_FORMAT`, `QUALITY_COMPLEXITY`, `PRACTICE_SECURITY` (regex reused), `DEPS_AUDIT`, `QUALITY_COVERAGE`, `ARCH_CIRCULAR`, `PRACTICE_TEST_MIRROR`, `PRACTICE_TEST_SCENARIO_NAMING`, `QUALITY_DIFF_SIZE` (git, reused), `TOOL_*` + `FILE_EXISTS_*`/`DIR_EXISTS_*` |
| **(b) À adapter** (intent holds, but mapped tool is coarser or needs reimplementation on the TS AST) | 17 | `QUALITY_TYPE`, `QUALITY_SECURITY`, `DEPS_HYGIENE`, `QUALITY_DEAD_CODE`, `ARCH_GOD_CLASS`, `ARCH_COUPLING`, `ARCH_DUPLICATION`, `PRACTICE_BARE_EXCEPT`, `PRACTICE_BLOCKING_IO`, `PRACTICE_DOCSTRING`, `STRUCTURE_TESTS_PYRAMID`, `STRUCTURE_PYPROJECT`, `TEST_QUALITY_DUPLICATE_TESTS`, `TEST_QUALITY_FILE_NAMING`, `TEST_QUALITY_NO_PACKAGE_SYMBOL`, `TEST_QUALITY_PRIVATE_IMPORTS`, `TEST_QUALITY_PYRAMID_LEVEL`, `TEST_QUALITY_TAUTOLOGY` |
| **(c) Svelte-spécifiques nouvelles** | 3 | `SVELTE_CHECK`, `SVELTE_A11Y`, `STRUCTURE_SVELTEKIT_CONFIG` |
| **(d) Sans équivalent (drop)** | 0 | — every Python intent has a Node/Svelte target |

> Note: the `(a)`+`(b)` total (28) plus the multi-instance `TOOL_*`/`FILE_EXISTS_*`
> families covers all 31 registered classes; counts above bucket by intent, not by
> instance. The four largest reimplementation efforts (no off-the-shelf tool, must
> walk the TS/Svelte AST via `ts-morph` or the TS compiler API) are the four
> `test_quality` structural rules: `DUPLICATE_TESTS`, `FILE_NAMING`,
> `NO_PACKAGE_SYMBOL`, `PRIVATE_IMPORTS`, `PYRAMID_LEVEL`, `TAUTOLOGY`.

### Portability by category

| catégorie | rules | 1:1 | adapté | nouveau | drop |
|---|---|---|---|---|---|
| lint | LINT, FORMAT, DEAD_CODE, DIFF_SIZE | 3 | 1 | 0 | 0 |
| type | TYPE | 0 | 1 | +1 (SVELTE_CHECK) | 0 |
| complexity | COMPLEXITY | 1 | 0 | 0 | 0 |
| security | QUALITY_SECURITY, PRACTICE_SECURITY | 1 | 1 | 0 | 0 |
| deps | AUDIT, HYGIENE | 1 | 1 | 0 | 0 |
| testing | COVERAGE | 1 | 0 | 0 | 0 |
| architecture | CIRCULAR, GOD_CLASS, COUPLING, DUPLICATION | 1 | 3 | 0 | 0 |
| practices | BARE_EXCEPT, BLOCKING_IO, DOCSTRING, MIRROR, SCENARIO_NAMING | 2 | 3 | 0 | 0 |
| test_quality | DUPLICATE_TESTS, FILE_NAMING, NO_PACKAGE_SYMBOL, PRIVATE_IMPORTS, PYRAMID_LEVEL, TAUTOLOGY | 0 | 6 | 0 | 0 |
| structure | TESTS_PYRAMID, PYPROJECT (+ FILE/DIR_EXISTS) | 1 | 2 | +1 (SVELTEKIT_CONFIG) | 0 |
| tooling | TOOL_* | 1 | 0 | +1 (SVELTE_A11Y is lint, not tooling) | 0 |

## Outils Node/Svelte requis

Binaries the Node/Svelte rule set would invoke (one per intent, mirroring how the
Python rules shell out to ruff/mypy/bandit/…):

| Outil npm | Remplace | Catégories servies |
|---|---|---|
| `eslint` (+ `typescript-eslint`, `eslint-plugin-svelte`, `eslint-plugin-sonarjs`, `eslint-plugin-security`, `eslint-plugin-jsdoc`) | ruff, radon/complexipy (cog), bandit (partial), docstring | lint, complexity, security, practices |
| `prettier` (+ `prettier-plugin-svelte`) | ruff format | lint (FORMAT) |
| `tsc` (TypeScript) | mypy | type |
| `svelte-check` | mypy (`.svelte` half) | type (Svelte) |
| `vitest` (+ `@vitest/coverage-v8` or istanbul) | pytest + pytest-cov | testing (COVERAGE), and host for test_quality test discovery |
| `npm audit` / `pnpm audit` / `yarn npm audit` | pip-audit | deps (AUDIT) |
| `depcheck` and/or `knip` | deptry, axm-ast dead-code | deps (HYGIENE), lint (DEAD_CODE) |
| `madge` (and/or `dependency-cruiser`) | in-house import-graph SCC | architecture (CIRCULAR, COUPLING) |
| `jscpd` | in-house AST clone hashing | architecture (DUPLICATION) |
| `ts-morph` / TS compiler API (library, not a CLI) | in-house AST walks | architecture (GOD_CLASS), all `test_quality` structural rules |
| `git` (already required) | git | lint (DIFF_SIZE) — reused unchanged |
| Svelte compiler `a11y-*` warnings | — (net-new) | lint (SVELTE_A11Y) |

> Package-manager-aware: detect `package-lock.json` / `pnpm-lock.yaml` / `yarn.lock`
> to pick the `audit` flavor and the runner (`npx`/`pnpm dlx`), the same way the Python
> rules resolve the project venv via `run_in_project` / `find_venv`.
