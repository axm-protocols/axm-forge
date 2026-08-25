# Node/TypeScript & Svelte/SvelteKit — Code Quality & Tooling Research (2025–2026)

> **Purpose.** Define automated audit rules for a home-grown architecture/quality linter that **invokes CLIs and SCORES their machine-readable output** — the Node/Svelte equivalent of what `ruff`/`mypy`/`bandit`/`pytest`/`deptry` do in Python.
>
> **Scoring doctrine (cross-cutting, read first).** Two invariants govern every dimension below:
> 1. **The exit code is the verdict; the parsed JSON is only the score breakdown — never invert that.** Exit codes conflate "policy violation" with "tool crashed" (notably Prettier exit 2, dependency-cruiser exit = error-count, knip exit 2). Always distinguish *tool error* (inconclusive) from *findings* (real).
> 2. **Always verify the tool actually processed the expected files.** Non-empty results, file-count sanity, `tsc --listFiles`. This defeats the entire "exit 0 on nothing checked" family of false-greens — the dominant failure mode of a naive scorer.
>
> **Systemic false-green (dimensions 7, 9, 12).** Unresolved TS/Svelte path aliases (`$lib`, `@/`). Pre-resolve config before any tool runs: `svelte-kit sync` (generates `.svelte-kit/tsconfig.json` + `$lib` aliases), pass `--ts-config`/`tsConfig` to madge & dependency-cruiser, pass `--tsconfig` to svelte-check.
>
> Research date: 2026-06. Tools to prioritise are those with **JSON / machine-readable output**.

---

## Dimension index & retained tool (quick table)

| # | Dimension | Retained CLI | JSON command (core) | Threshold / gate |
|---|---|---|---|---|
| 1 | Lint | ESLint v9 flat + typescript-eslint v8 + eslint-plugin-svelte | `eslint . --format json` | 0 errors; `--max-warnings 0` (strict) |
| 2 | Type-check | `tsc --noEmit` + `svelte-check` | `tsc --noEmit --pretty false` / `svelte-check --output machine-verbose` | 0 errors, strict mode |
| 3 | Complexity | ESLint `complexity` + eslint-plugin-sonarjs | `eslint . --format json` | cyclomatic < 10, cognitive < 15 |
| 4 | Security | npm/pnpm audit + eslint-plugin-security + gitleaks | `npm audit --json` / `gitleaks dir . --report-format json` | 0 high/critical vulns; 0 secrets |
| 5 | Dependencies | **knip** (depcheck archived) | `knip --reporter json` | 0 unused/unlisted |
| 6 | Tests | Vitest + Playwright | `vitest run --reporter=json` / `--coverage.reporter=json-summary` | coverage ≥ 80%, `numTotalTests > 0` |
| 7 | Architecture | madge (cycles) + dependency-cruiser (policy) | `madge --circular --json` / `depcruise --output-type json` | 0 cycles |
| 8 | Dead code | **knip** (ts-prune deprecated) | `knip --exports --reporter json` | 0 unused exports/files |
| 9 | Structure/manifest | JSON parse + `publint` | read `package.json`/`tsconfig.json`; `publint --json` | required fields present, `strict: true` |
| 10 | Duplication | jscpd | `jscpd --reporters json` | < 3–5%, min-tokens 50 |
| 11 | Formatting | Prettier + prettier-plugin-svelte | `prettier --list-different .` | 0 diffs |
| 12 | Svelte practices | svelte-check (a11y) + eslint-plugin-svelte (runes) | `svelte-check --output machine` + `eslint . --format json` | 0 a11y warnings (promoted), runes hygiene |

> **One ESLint run, many dimensions.** Dimensions 1, 3 (complexity + cognitive), 4 (eslint-plugin-security), and 12 (svelte rules) all come from a **single** `eslint . --format json` invocation. Partition `results[*].messages[*]` by `ruleId`.

---

## DIMENSION 1 — Lint

### De-facto CLI (2025–2026)
- **ESLint v9+ with flat config** (`eslint.config.js`/`.mjs`/`.ts`). Flat config is the **default** in v9; legacy `.eslintrc` is deprecated/removed-as-default.
- **typescript-eslint v8** via `tseslint.config()`/`defineConfig()`. Flagship: stable **project service** (`parserOptions.projectService: true`) — faster than the old `project` glob for typed linting.
- **eslint-plugin-svelte** (AST-based via `svelte-eslint-parser`); superseded the deprecated `eslint-plugin-svelte3`.

```javascript
// eslint.config.mjs — canonical typed TS config
import js from '@eslint/js';
import { defineConfig } from 'eslint/config';
import tseslint from 'typescript-eslint';

export default defineConfig({
  files: ['**/*.{js,ts}'],
  extends: [
    js.configs.recommended,
    tseslint.configs.recommended,
    tseslint.configs.recommendedTypeChecked,  // type-aware rules
    tseslint.configs.stylisticTypeChecked,
  ],
  languageOptions: {
    parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
  },
});
```
Tiers: `recommended` → `recommendedTypeChecked` (correctness), `strict` → `strictTypeChecked` (opinionated), `stylistic` → `stylisticTypeChecked`.

### Exact JSON command
```bash
eslint . --format json                 # bare array of file-result objects
eslint . --format json-with-metadata   # { results: [...], metadata: { rulesMeta } }
```
Both formatters are **built-in**. JSON shape (per file):
```json
{
  "filePath": "/abs/src/foo.ts",
  "messages": [{ "ruleId": "@typescript-eslint/no-unused-vars", "severity": 2,
                 "message": "'x' is defined but never used.", "line": 10, "column": 7 }],
  "errorCount": 1, "warningCount": 0, "fixableErrorCount": 0
}
```
**Severity field:** `2` = error, `1` = warning, `0` = off (never emitted).

### Reliable counting + thresholds
Sum per-file counts from JSON — do **not** scrape stdout text:
```bash
eslint . --format json | jq '[.[].errorCount] | add'    # total errors
eslint . --format json | jq '[.[].warningCount] | add'  # total warnings
```
- **0 errors** = hard gate (universal in CI).
- **Warnings:** strict stance is `--max-warnings 0` ("ESLint warnings are an anti-pattern" — promote to error or delete). For a scoring linter: errors block, warnings are a graded penalty.
- Type-aware rules (`recommendedTypeChecked`) expected on — turning them off is a quality smell.

### eslint-plugin-svelte vs svelte-check (complementary, run BOTH)
| | eslint-plugin-svelte | svelte-check |
|---|---|---|
| Engine | ESLint + `svelte-eslint-parser` (template AST) | TS compiler + Svelte compiler |
| Domain | **Code quality / style / lint** | **Type safety + Svelte diagnostics** |
| Catches | Naming, code patterns, template best-practices, reactive-statement misuse, stylistic consistency | Type errors in `<script lang="ts">`, unresolved imports, prop/type mismatches, **unused CSS**, **a11y compiler hints** |
| Misses | Type errors, cross-file types, unused CSS | Variable naming, code-style rules |

Rule of thumb: **svelte-check = "does it type-check & compile cleanly?"; eslint-plugin-svelte = "is it written well/consistently?"**

### FALSE-GREEN pitfalls
1. **Exit 0 when no files matched.** Bad/over-narrow glob matches zero files, exits 0, returns `[]` → perfect score on an unlinted project. Mitigate: assert results non-empty + file-count sanity; don't pass `--no-error-on-unmatched-pattern` in audit mode.
2. **Config error swallowed.** A broken flat config exits **2** ("config/internal error") with no `errorCount` → naive scorer reports green. Treat exit `2` as hard FAIL distinct from lint errors (exit `1`).
3. **`--quiet` hides the denominator.** `--quiet` only runs error-level rules → "0 warnings" always. Never use in an audit.
4. **`.eslintignore` not read under flat config** (must move to `ignores` block); half-migrated repos silently lint a subset.
5. **Typed-linting silently degraded.** If `projectService`/`project` isn't wired, `*TypeChecked` rules are no-ops. Assert the type-checked config is active.
6. **JSON truncation on huge outputs** (reported in Nx wrappers). Use `--output-file` and validate it parses.

**Sources:** <https://eslint.org/docs/latest/use/formatters/> · <https://eslint.org/docs/latest/use/command-line-interface> · <https://eslint.org/docs/latest/use/configure/configuration-files> · <https://typescript-eslint.io/getting-started/typed-linting/> · <https://typescript-eslint.io/blog/announcing-typescript-eslint-v8/> · <https://sveltejs.github.io/eslint-plugin-svelte/> · <https://github.com/eslint/eslint/issues/16701> · <https://dev.to/thawkin3/eslint-warnings-are-an-anti-pattern-33np>

---

## DIMENSION 2 — Type-check

### De-facto CLI
- **`tsc --noEmit`** for `.ts`/`.tsx` (exit 0 = clean, 1 = errors). React's `.tsx` is covered natively — no extra pass.
- **`svelte-check`** (or **`sv check`**, the Svelte CLI wrapper requiring the `svelte-check` package) for `.svelte` — `tsc` alone **cannot** type-check inside `.svelte`. Mandatory for SvelteKit.

### Exact machine-readable commands
**tsc has NO native JSON.** Use `--pretty false` (strips ANSI, one diagnostic per line):
```bash
tsc --noEmit                  # the gate
tsc --noEmit --pretty false   # machine-parseable lines
```
Line format: `path(line,col): error TS<code>: <message>` + trailing summary `Found N errors in M files.` Third-party parser: `@aivenio/tsc-output-parser`.

**svelte-check has a real machine mode:**
```bash
svelte-check --output machine --threshold error            # errors only, space-separated rows
svelte-check --output machine-verbose --tsconfig ./tsconfig.json  # NDJSON, one JSON per diagnostic (incl. TS code)
npx sv check --output machine --threshold error
```
Options: `--output <human|human-verbose|machine|machine-verbose>`, `--threshold <error|warning>`, `--tsconfig`, `--fail-on-warnings`, `--compiler-warnings "code:error|ignore,..."`, `--diagnostic-sources <js|svelte|css>`.

### Reliable counting
**tsc** — count by error-code pattern, gated by exit code:
```bash
tsc --noEmit --pretty false | grep -c ": error TS"   # regex anchor: ": error TS\d+:"
```
The summary `Found N errors` gives N. **Exit code is the verdict** — a non-zero exit with zero grep-matched lines = abnormal crash = hard FAIL.

**svelte-check** machine modes:
- `machine`: `<timestamp> <ERROR|WARNING> "<file>" <line>:<col> "<message>"`
- `machine-verbose` (best for scoring — carries TS `code` + ranges): `<ts> {"type":"ERROR","fn":"x.svelte","start":{...},"end":{...},"message":"...","code":2307,"source":"js"}`
- Summary line (both): `<ts> COMPLETED 20 FILES 21 ERRORS 1 WARNINGS 3 FILES_WITH_PROBLEMS` — parse this for totals.

### Thresholds
- **tsc: 0 errors, `strict: true`.** Flag `strict: false` as debt even at 0 errors ("0 errors in loose mode" ≠ "0 errors in strict mode").
- **svelte-check: 0 errors.** Warnings (unused CSS, a11y) commonly allowed but tracked; `--fail-on-warnings` is the strict stance.

### FALSE-GREEN pitfalls
1. **`skipLibCheck: true`** skips type-checking ALL `.d.ts` (incl. yours) → masks declaration bugs. Record whether it's on; consider an occasional `skipLibCheck: false` pass.
2. **Files excluded by tsconfig are never checked.** A typo in `include`/over-broad `exclude` → exit 0 on unchecked code. Cross-check via `tsc --listFiles --noEmit` against the source tree.
3. **Project references / `composite` + `--noEmit` misconfig.** A root tsconfig with empty `files`/`references`, or stale `.tsbuildinfo`, can exit 0 having checked **nothing**. Use `tsc -b --noEmit` for refs; validate visited files with `--listFiles`/`--verbose`; clear `.tsbuildinfo` in a clean audit.
4. **svelte-check pointed at wrong tsconfig.** Needs the app config that `extends` `.svelte-kit/tsconfig.json` (run `svelte-kit sync` first) and includes `.svelte` + `$lib` aliases.
5. **Counting grep instead of exit code (tsc).** Treat non-zero exit + zero grep matches as hard FAIL.

**Sources:** <https://github.com/sveltejs/language-tools/blob/master/packages/svelte-check/README.md> · <https://svelte.dev/docs/cli/sv-check> · <https://www.testim.io/blog/typescript-skiplibcheck/> · <https://github.com/microsoft/TypeScript/issues/41883> · <https://moonrepo.dev/docs/guides/javascript/typescript-project-refs> · <https://www.npmjs.com/package/@aivenio/tsc-output-parser>

---

## DIMENSION 3 — Complexity

### Cyclomatic — ESLint built-in `complexity` rule
- **Core rule, no plugin.** ruleId in JSON: `"complexity"` (no prefix).
- **OFF by default** (NOT in `eslint:recommended`). **Default threshold when enabled with no arg is `20`, not 10** — must set `max` explicitly.
```js
// eslint.config.js
export default [{ rules: { complexity: ["error", { max: 10 }] } }];  // "max", not deprecated "maximum"
```
Variants: `"classic"` (McCabe, default), `"modified"` (a `switch` adds +1 regardless of case count).

### Cognitive — eslint-plugin-sonarjs `cognitive-complexity`
- ruleId in JSON: `"sonarjs/cognitive-complexity"` (plugin-prefixed). **Default threshold = 15.**
- Penalises nesting depth + chained booleans (catches McCabe false-negatives: deep but low-branch code).
- **Requires flat-config plugin registration.**
```js
import sonarjs from "eslint-plugin-sonarjs";
export default [
  sonarjs.configs.recommended,
  { plugins: { sonarjs }, rules: { "sonarjs/cognitive-complexity": ["error", 15] } },
];
```
> Note: standalone `SonarSource/eslint-plugin-sonarjs` repo archived 2024-10-03 (rules consolidated into `SonarSource/SonarJS` `packages/jsts`), but the **npm package is still published/maintained**; ruleId + default unchanged.

### SonarSource 2025 thresholds — CONFIRMED (= AXM Python convention)
- **Cyclomatic < 10** ("simple, testable"); > 20 "overly complex"; acceptance floor = **10**.
- **Cognitive < 15** — SonarQube default per-function threshold.
- These map 1:1 to AXM Python: ruff C901 `max-complexity = 10` (cyclomatic) + complexipy `< 15` (cognitive).

### Extracting per-function findings (same JSON as Dimension 1)
```bash
eslint . --format json --output-file eslint-report.json
```
Each message: `{ "ruleId": "complexity" | "sonarjs/cognitive-complexity", "severity": 2, "message": "Function 'bar' has a complexity of 14. Maximum allowed is 10.", "line": 42, "column": 1 }`. The numeric value lives in `message` text (parse the integers — ESLint doesn't expose it structured). `filePath` + `line` locate the function.

### FALSE-GREEN pitfalls
- Both rules **OFF until explicitly enabled** → zero findings on a project with no rule = false green.
- Core `complexity` default is **20 not 10** — enable without `max` and you silently use the loose threshold.
- `sonarjs/*` needs the plugin **registered in flat config**; a leftover `.eslintrc` on ESLint v9 may not load it.
- Cyclomatic & cognitive disagree by design — **score both independently**, never treat one as a proxy.

**Sources:** <https://eslint.org/docs/latest/rules/complexity> · <https://github.com/SonarSource/eslint-plugin-sonarjs/blob/master/docs/rules/cognitive-complexity.md> · <https://www.sonarsource.com/resources/library/cyclomatic-complexity/> · <https://docs.sonarsource.com/sonarqube-server/user-guide/code-metrics/metrics-definition>

---

## DIMENSION 4 — Security

### npm / pnpm audit
```bash
# npm (auditReportVersion 2)
npm audit --json                  # full report, all dep types
npm audit --json --omit=dev       # production only (modern; legacy: --production)
npm audit --audit-level=high      # EXIT-CODE GATE only — JSON still has all vulns
npm audit signatures --json       # SEPARATE: provenance/signature check, NOT vuln scan

# pnpm
pnpm audit --json
pnpm audit --json --prod          # -P production only
pnpm audit --json --audit-level high  # REPORT FILTER (omits low/moderate from JSON!)
```
**JSON shape (npm):** `metadata.vulnerabilities.{info,low,moderate,high,critical,total}` + per-package `vulnerabilities` (`severity`, `isDirect`, `via[]`, `fixAvailable`). **Score from `metadata.vulnerabilities` counts.** Severity vocab: `info|low|moderate|high|critical`.
**Exit codes:** `0` = clean at/above threshold; `1` = vulns found; `2` = bad args.

**Critical npm-vs-pnpm difference:**
- npm `--audit-level` = **exit-code gate** (JSON still contains all vulns regardless).
- pnpm `--audit-level` = **report FILTER** ("only print advisories ≥ severity"). Run pnpm **without** `--audit-level` (or `--audit-level low`) for the full picture. pnpm ignores via GHSA IDs in `pnpm-workspace.yaml` `auditConfig.ignoreGhsas`.

### eslint-plugin-security (same ESLint JSON, ruleId `security/detect-*`)
```js
import pluginSecurity from "eslint-plugin-security";
export default [ pluginSecurity.configs.recommended ];
```
Rules: `detect-object-injection`, `detect-non-literal-fs-filename`, `detect-non-literal-regexp`, `detect-eval-with-expression`, `detect-child-process`, `detect-unsafe-regex`, `detect-possible-timing-attacks`, `detect-pseudoRandomBytes`, `detect-non-literal-require`, `detect-bidi-characters`, etc.
**Reputation:** the plugin itself says "finds a lot of false positives which need triage." Worst: `detect-object-injection` (fires on every `obj[key]`), `detect-non-literal-fs-filename`. **Score as warnings/advisory, NOT hard gate**; allow per-rule allow-listing.

### Secret detection — gitleaks (standard) > trufflehog (deep)
```bash
gitleaks dir . --report-format json --report-path gitleaks.json --exit-code 1  # working tree, no history, no network
gitleaks detect --source . --report-format json --report-path gitleaks.json    # git history
trufflehog filesystem . --json --fail   # --fail needed or it exits 0 with findings (exit 183 on hit)
```
gitleaks exit `1` when leaks found (configurable). Use gitleaks as the fast standard gate; trufflehog as optional verified deep pass (`--results=verified`).

### SvelteKit security (static detection)
**Server-only module** if ANY: filename ends `.server.{js,ts}`; lives under `$lib/server/`; is `$env/static/private` or `$env/dynamic/private`; is `$app/server`.
- `$env/static/private` / `$env/dynamic/private` → server-only.
- `$env/static/public` / `$env/dynamic/public` → `PUBLIC_`-prefixed, **shipped to browser** — never a secret.
- `+page.server.ts` / `+layout.server.ts` / `+server.ts` / `hooks.server.ts` → server-only (may import private).
- `+page.ts` / `+layout.ts` / `*.svelte` → **universal** (server + client) → importing server-only here is the canonical leak.

**Static rules to implement:**
1. Flag import of `$env/*/private` / `$app/server` / `$lib/server/*` / `*.server.{js,ts}` from any universal/client file.
2. **Resolve transitively** — a client file importing a clean module that itself imports server-only is a violation (matches SvelteKit's own rule; the whole import chain is poisoned).
3. Flag secrets under `PUBLIC_`-prefixed env.
SvelteKit's bundler throws a build error: `Cannot import $lib/server/secrets.ts into code that runs in the browser...`

### FALSE-GREEN pitfalls
1. **npm `--audit-level` = gate vs pnpm = filter** — same flag, opposite meaning. Score from full `metadata.vulnerabilities`, normalise per-tool.
2. **audit resolves the lockfile + registry, NOT `node_modules`** — stale/missing lockfile → `ENOLOCK` (false red) or wrong tree (false green).
3. **`--omit=dev`/`--production` hides build-time vulns** (webpack-dev-server etc.) — legit de-noise but a real CI-RCE risk; decide policy explicitly.
4. **Presence ≠ reachability** — ~99% FP rate on app trees. Rank by severity + `isDirect` + `fixAvailable`, not raw totals.
5. **`npm audit signatures` is a different check** (provenance) — don't conflate.
6. **audit ignores `peerDependencies`** — a peer-only vuln is a blind spot.
7. **SvelteKit illegal-import detection is DISABLED under test** (`process.env.TEST === 'true'`) — a green `vitest` run does NOT prove no leak. Run the import-graph rule independently (against `vite build` or your own AST pass).

**Sources:** <https://docs.npmjs.com/cli/v11/commands/npm-audit/> · <https://pnpm.io/cli/audit> · <https://overreacted.io/npm-audit-broken-by-design/> · <https://github.com/eslint-community/eslint-plugin-security> · <https://github.com/gitleaks/gitleaks> · <https://svelte.dev/docs/kit/server-only-modules> · <https://svelte.dev/docs/kit/$env-static-private>

---

## DIMENSION 5 — Dependencies

### De-facto CLI: knip (depcheck ARCHIVED 2025-06-16, recommends knip)
| Tool | Status | Detects |
|---|---|---|
| **knip** | **Recommended / maintained** | unused files, unused deps, **unlisted (missing) deps**, unused devDeps, unused optional peerDeps, unused binaries, unresolved imports, duplicate deps, unused exports/types — one run, native monorepo/workspace support |
| depcheck | **Archived 2025-06-16** ("switch to Knip") | unused deps/devDeps, missing deps; **no workspace concept** |
| ts-prune | Archived (recommends Knip) | unused exports only |

### Exact JSON commands
```bash
knip --reporter json                          # full surface
knip --dependencies --reporter json           # scope to deps (dependencies,unlisted,binaries,unresolved,catalog)
knip --reporter json --no-exit-code           # CI: emit JSON, never fail — parse + score yourself
```
JSON: single top-level `issues[]`; each entry is one file with issue-type keys (each an array; empty/absent = clean): `files`, `dependencies`, `devDependencies`, `optionalPeerDependencies`, `unlisted`, `binaries`, `unresolved`, `exports`, `types`, `enumMembers`, `namespaceMembers`, `duplicates`, `catalog`.
```json
{ "issues": [
  { "file": "package.json", "dependencies": [{"name":"lodash"}], "unlisted": [{"name":"rimraf"}],
    "devDependencies": [{"name":"@types/unused"}], "unresolved": [{"name":"./missing"}] } ] }
```
**Outdated:** `npm outdated --json` (exit 1 when any outdated) — object keyed by package: `{current, wanted, latest, type}`. Score patch/minor = `wanted !== current`; major = `latest !== wanted`.

### Thresholds / error semantics
- knip exit: `0` clean, **`1` = issues found**, **`2` = exception** (tool failure — NOT a finding).
- `--max-issues N` (default 0): exit 1 only above N. `--no-exit-code`: always 0 (parse JSON). `--treat-config-hints-as-errors`: make config drift fail.

### FALSE-GREEN pitfalls
- **Monorepo:** depcheck has no workspace concept → running at root misses per-package deps. Use knip `--workspace`; run twice (default + `--production`); `--strict` isolates each workspace to its direct deps (catches hoist-satisfied deps).
- **peerDependencies FP:** knip models `optionalPeerDependencies` separately; depcheck does not → noise.
- **Dynamic imports missed** — `import(variable)`, config-string refs. Always allow an ignore-list.
- **Exit 2 (knip) / `invalidFiles` (depcheck)** = parse/permission failure = empty findings = false green. Score as tool-error, not pass.

**Sources:** <https://knip.dev/explanations/comparison-and-migration> · <https://github.com/depcheck/depcheck> · <https://knip.dev/features/reporters> · <https://knip.dev/reference/cli> · <https://knip.dev/guides/using-knip-in-ci> · <https://docs.npmjs.com/cli/v11/commands/npm-outdated>

---

## DIMENSION 6 — Tests

### De-facto: Vitest (unit/component) + Playwright (e2e)
Vitest is bundled by default in SvelteKit (`sv add vitest`). Coverage default provider **v8**; since **Vitest 3.2.0** v8 uses AST-based remapping → reports "identical to Istanbul" (v8 now both fast and accurate).

### JSON commands + shapes
**Test results:**
```bash
vitest run --reporter=json --outputFile=./vitest-results.json
```
`{ numTotalTests, numPassedTests, numFailedTests, numTotalTestSuites, numFailedTestSuites, success, testResults[], coverageMap? }` (Jest-`--json`-compatible). Score: `success`, `numFailedTests`, **assert `numTotalTests > 0`**.

**Coverage:**
```bash
vitest run --coverage --coverage.provider=v8 --coverage.reporter=json-summary
# pair with --coverage.reporter=json for the per-line map
```
`coverage-summary.json`: `total.{lines,statements,functions,branches}.pct` + per-file keys. Score `total.<metric>.pct`.

**Config-side thresholds (`vitest.config.ts`):**
```ts
coverage: {
  provider: 'v8', reporter: ['text','json-summary','json'],
  thresholds: { lines: 80, functions: 80, branches: 80, statements: 80,
                perFile: true, autoUpdate: false },  // autoUpdate:false in CI!
}
```

**e2e — Playwright:**
```bash
PLAYWRIGHT_JSON_OUTPUT_NAME=pw-results.json npx playwright test --reporter=json
```
`stats.{expected,unexpected,flaky,skipped}`. Pass = `stats.unexpected === 0`; treat `stats.flaky > 0` as degraded.

**Component testing:** `@testing-library/svelte` (jsdom + Vitest) is still the fresh-scaffold default; 2025 recommended direction is **`vitest-browser-svelte`** (Vitest Browser Mode, real browser, handles Svelte 5 reactivity). Accept either.

### Naming & layout (SvelteKit 2025–2026)
- **Extension:** `*.test.ts` is the idiomatic default (scaffolder generates it); `*.spec.ts` equally valid, less common here. Vitest also accepts `__tests__/`.
- **Layout:** **colocation in `src/` next to source** is the SvelteKit-recommended idiom (mirrored `tests/` also supported). e2e (Playwright) → separate `tests/`/`e2e/`.
- **Dual-project split (canonical):** `vitest.config.ts` `projects: [client (jsdom, **/*.svelte.test.ts), server (node, **/*.test.ts excluding svelte)]`.

### Threshold convention + FALSE-GREEN pitfalls
- **80%** across lines/branches/functions/statements; tighten critical modules via glob thresholds; `perFile: true` prevents one fat file masking a bare one.
- **#1 false-green — no tests collected:** `passWithNoTests: true` (or `--passWithNoTests`) makes Vitest exit 0 with zero tests → a test-less package "passes." **Independently assert `numTotalTests > 0`** from JSON; don't trust the exit code.
- **v8 < 3.2.0** can be optimistic vs istanbul — record the Vitest version.
- **`coverage.all`** off → pct only reflects imported files (excludes dead/never-imported modules = false green).
- **`autoUpdate: true`** silently rewrites the floor — never in CI.
- **Coverage & test-results are separate artifacts** — opt into both reporters.
- **e2e flakiness:** retries inflate green — score `stats.flaky` separately.

**Sources:** <https://vitest.dev/guide/reporters> · <https://vitest.dev/config/coverage> · <https://vitest.dev/guide/coverage> · <https://playwright.dev/docs/test-reporters> · <https://github.com/vitest-dev/vitest/issues/2304> · <https://svelte.dev/docs/svelte/testing> · <https://kit.svelte.dev/docs/project-structure>

---

## DIMENSION 7 — Architecture (import cycles)

### De-facto: madge (cycles) + dependency-cruiser (policy)
| Tool | Best for |
|---|---|
| **madge** | Quick cycle smoke-test / one-shot gate (zero-config, fast, single concern) |
| **dependency-cruiser** | Full ruleset / layering / orphan / architecture contract (`.dependency-cruiser.js`) |

### JSON commands + shapes
**madge:**
```bash
npx madge --circular --json --extensions ts,tsx --ts-config ./tsconfig.json src/
```
`--circular --json` → **array of arrays of file paths** (each inner array = one cycle): `[["a.ts","b.ts"],["c.ts","d.ts","e.ts"]]`. (Bare `madge --json` → full graph object `{file: [deps]}`.) Score: `cycle_count = len(result)`; gate `== 0`. Exit non-zero when ≥1 cycle.

**dependency-cruiser:**
```bash
npx depcruise --init                                              # writes .dependency-cruiser.js
npx depcruise src --config .dependency-cruiser.js --output-type json > cruise.json
```
JSON: `{ modules[], summary: { violations[{from,to,rule:{name,severity},cycle?}], error, warn, info, ignore, totalCruised } }`. **Score off `summary.error`/`summary.warn`/`violations[].rule.name`.** Exit code = number of `error`-severity violations (`warn`/`info` don't affect exit → advisory). Default ruleset: `no-circular`, `no-orphans`, `no-deprecated-*`, `not-to-unresolvable`, `no-non-package-json`, `not-to-dev-dep`, `optional-deps-used`, `peer-deps-used`. Add layering by hand:
```js
{ name: 'ui-not-to-server', severity: 'error',
  from: { path: '^src/lib/components' }, to: { path: '^src/lib/server' } }
```

### Barrel files (`index.ts` re-exports) — anti-pattern 2025–2026
- **Why they hurt:** (a) tree-shaking defeat (importing one symbol pulls the whole barrel graph into the bundle/test runner); (b) circular deps (A→B→A via the same barrel → runtime `undefined`); (c) build/cold-start perf (Next.js shipped `optimizePackageImports` to mitigate).
- **Detection:** flag `index.{ts,js}` files that are pure re-export façades (every top-level statement is `export … from` / `export *`); cross-check abnormally high fan-in via dependency-cruiser. `export *` is the worst offender. Remedy in the message: direct imports + `"sideEffects": false`.

### SvelteKit structure invariant
`src/lib/` (`$lib`), `src/lib/server/` (`$lib/server`, server-only), `src/routes/` (filesystem routing), `src/params/`, `hooks.{client,server}.js`, `svelte.config.js`, `vite.config.js`, `tsconfig.json` extends `.svelte-kit/tsconfig.json`. **Enforceable rule:** nothing under `$lib/server` may be imported from client code (compiler enforces it; a dependency-cruiser `forbidden` rule makes it a scored gate).

### FALSE-GREEN pitfalls
- **TS path aliases unresolved by madge** → cycles through `$lib`/`@/` invisible unless `--ts-config ./tsconfig.json`. Run after `svelte-kit sync` (aliases in `.svelte-kit/tsconfig.json`).
- **madge misses transitive cycles** by default (first-level/direct) — prefer dependency-cruiser `no-circular` for exhaustive coverage.
- **Type-only imports create false cycles** in dependency-cruiser when `tsPreCompilationDeps: true` (counts `import type` edges that vanish at runtime). Set `false`/`"specify"` to exclude — or keep `true` deliberately to forbid type-level cycles. Biggest false-red/green disagreement between the two tools.
- **`.svelte` files** need the resolver to know the extension (`enhancedResolveOptions`) or component imports are dropped.

**Sources:** <https://github.com/pahen/madge> · <https://github.com/sverweij/dependency-cruiser/blob/main/doc/rules-reference.md> · <https://github.com/sverweij/dependency-cruiser/blob/main/doc/output-format.md> · <https://dev.to/elmay/the-barrel-trap-how-i-learned-to-stop-re-exporting-and-love-explicit-imports-3872> · <https://github.com/vercel/next.js/discussions/92926> · <https://svelte.dev/docs/kit/project-structure>

---

## DIMENSION 8 — Dead code

### De-facto: knip (ts-prune DEPRECATED, recommends knip)
ts-prune is archived; it could not detect unused deps or mutually-recursive dead code, and emits **plain text only** (`path:line - name`) — unsuitable for JSON scoring. **knip is the successor:** unused files, exports/types, enum/namespace members, duplicate exports, with monorepo awareness + auto-fix.

### JSON commands
```bash
knip --reporter json                          # whole dead-code surface
knip --exports --reporter json                # exports,types,enumMembers,namespaceMembers,duplicates
knip --files --reporter json                  # unused files only
knip --include files,exports,types,duplicates --reporter json
```
Same `issues[]` shape as Dimension 5; for dead code score per-file keys: `files` (bare `{file}` entry), `exports`, `types`, `enumMembers`, `namespaceMembers`, `duplicates`. Each export item: `{name, line, col, pos}`.

### Thresholds / error semantics
Same engine as Dimension 5: exit `1` = found, `2` = exception, `0` = clean. `--max-issues N` threshold; `--no-exit-code` to score JSON directly. Per-issue-type severity via `knip.json` `rules` (`error`/`warn`/`off`) for phased adoption.

### FALSE-GREEN / FALSE-POSITIVE pitfalls
- **Entry-point config is everything** — wrong `entry`/`project` globs → real entries reported unused (FP) or downstream files look reachable (FN). Surface "did knip resolve entry points?".
- **Public API surface FP** — published exports consumed by external packages flagged "unused." Mark as entry exports or allowlist the public surface.
- **Re-exports / barrels** confuse reachability — a barrel that *is* an entry keeps everything alive (hiding real dead code = false green). Verify barrel classification.
- **Dynamic usage** (string-keyed, DI, framework auto-registration) → FP; tag/ignore.
- **Exit 2 = false green** — exception returns empty findings; never score as "no dead code."

**Sources:** <https://knip.dev/explanations/comparison-and-migration> · <https://knip.dev/typescript/unused-exports> · <https://knip.dev/features/rules-and-filters> · <https://levelup.gitconnected.com/dead-code-detection-in-typescript-projects-why-we-chose-knip-over-ts-prune-8feea827da35>

---

## DIMENSION 9 — Structure / manifest

### De-facto: read JSON + assert; optional `publint` (export-map validator) / `attw`
No single dominant manifest-linter CLI. Convention: **read `package.json` & `tsconfig.json` as JSON** (config, not code) and assert required fields. Layer **`publint --json`** for `exports`/types/ESM-CJS correctness (severity-tagged messages); **`@arethetypeswrong/cli`** for type-resolution.

### Required `package.json` fields (published, 2025–2026)
```jsonc
{
  "name": "@scope/pkg", "version": "1.2.3",
  "type": "module", "license": "MIT",
  "repository": { "type": "git", "url": "git+https://github.com/u/r.git" },
  "engines": { "node": ">=18" },
  "files": ["dist"],
  "sideEffects": false,
  "types": "./dist/index.d.ts",
  "exports": {
    ".": { "types": "./dist/index.d.ts", "import": "./dist/index.js",
           "require": "./dist/index.cjs", "default": "./dist/index.js" },
    "./package.json": "./package.json"
  },
  "main": "./dist/index.cjs", "module": "./dist/index.js"
}
```
**SvelteKit library** (svelte-package) adds `"svelte"` export condition + `"sideEffects": ["**/*.css"]` + `peerDependencies: { svelte: "^5.0.0" }`.

### tsconfig strict (assert present & true)
```jsonc
{ "extends": "./.svelte-kit/tsconfig.json",
  "compilerOptions": {
    "strict": true, "noUncheckedIndexedAccess": true, "noImplicitOverride": true,
    "noImplicitReturns": true, "exactOptionalPropertyTypes": true,
    "moduleResolution": "bundler", "verbatimModuleSyntax": true } }
```
Presence checks: `svelte.config.js` + `vite.config.ts` must exist for a SvelteKit project. For SvelteKit, `tsconfig.json` is thin (extends the generated config) — assert strict flags **after resolving `extends`** (or `tsc --showConfig`).

### Severities
Boolean presence/shape assertions (no exit-code tool). Suggested: **error** for missing `name`/`version`/`license`/`exports`-or-`main`/`type` and `strict !== true`; **warn** for missing `engines`/`sideEffects`/`repository`/`files`.

### FALSE-GREEN pitfalls
- **`exports` map vs `main` fallback:** once `exports` exists it overrides `main` and **blocks every undeclared subpath** (`ERR_PACKAGE_PATH_NOT_EXPORTED`). Checking only `main` is a false green — validate the exports map; require `"./package.json": "./package.json"`.
- **Conditional-export ordering:** `"types"` FIRST, `"default"` LAST; `import`/`require` mutually exclusive, most-specific→least. Wrong order resolves the wrong file at runtime while still valid JSON.
- **ESM/CJS dual-package hazard:** separate `.mjs`/`.cjs` paths load the module twice (duplicate state, broken `instanceof`/singletons). Prefer ESM-only unless dual-publish is genuinely needed.
- **`strict: true` is not total** — doesn't enable `noUncheckedIndexedAccess` / `exactOptionalPropertyTypes`. Check those explicitly.
- **`extends` chains** — asserting flags on the literal file misses inherited values. Resolve the effective config (`tsc --showConfig`).

**Sources:** <https://nodejs.org/api/packages.html> · <https://hirok.io/posts/package-json-exports> · <https://www.typescriptlang.org/docs/handbook/modules/reference.html> · <https://svelte.dev/docs/kit/packaging> · <https://www.npmjs.com/package/@tsconfig/svelte>

---

## DIMENSION 10 — Duplication

### De-facto: jscpd
```bash
npx jscpd --reporters json --min-tokens 50 --min-lines 5 src/             # → ./report/jscpd-report.json
npx jscpd --reporters json --output ./report --threshold 5 --min-tokens 50 src/
```
JSON: `statistics.total.{percentage, percentageTokens, clones, duplicatedLines}` + `statistics.formats.<lang>` + `duplicates[]` (`format`, `lines`, `tokens`, `firstFile`, `secondFile`, `fragment`). **Score off `statistics.total.percentage`** (% duplicated lines).

### Thresholds
- `--threshold <n>`: if duplication **≥ threshold**, exits non-zero (CI gate). Convention: **3–5%** (5% lenient default, 3% stricter).
- `--min-tokens` default **50**, `--min-lines` default **5** — minimum clone size. 50 tokens is the de-facto baseline (raise to ~70 to reduce boilerplate noise).

### FALSE-GREEN / FALSE-RED pitfalls
- **Generated/vendored code inflates duplication** (lockfiles, `*.d.ts`, dist, snapshots). Exclude via `--ignore "**/*.d.ts,**/dist/**,**/*.snap"`. Prefer **narrow ignores + low threshold** over **broad scope + high threshold** (the latter hides real dupes).
- **`min-tokens` too high** misses small meaningful copy-paste; too low flags idiomatic patterns.
- **`.svelte` files:** ensure the svelte/html format is enabled or component dupes go uncounted — check `statistics.formats` includes expected languages.

**Sources:** <https://github.com/kucherenko/jscpd> · <https://jscpd.dev/> · <https://megalinter.io/latest/descriptors/copypaste_jscpd/>

---

## DIMENSION 11 — Formatting

### De-facto: Prettier + prettier-plugin-svelte
```bash
npx prettier --check .            # CI gate: human summary + list of unformatted
npx prettier --list-different .   # MACHINE: prints ONLY filenames that differ (pipe-friendly)
npx prettier --write .            # fix in place
```
`.prettierrc` declares plugins (Prettier 3 discovers via config):
```jsonc
{ "plugins": ["prettier-plugin-svelte", "prettier-plugin-tailwindcss"],  // tailwind MUST be last
  "overrides": [{ "files": "*.svelte", "options": { "parser": "svelte" } }] }
```

### Exit-code semantics (the scored signal)
| Exit | Meaning |
|---|---|
| **0** | All formatted → pass |
| **1** | Some files unformatted → fail (fixable) |
| **2** | Prettier errored (syntax/bad config/missing plugin) → infra failure, NOT a formatting verdict |
**Distinguish exit 1 (real) from exit 2 (crash).** Use `--list-different` to count/parse offending files. Formatting is binary — threshold = zero diffs.

### FALSE-GREEN pitfalls
- **prettier-plugin-svelte not installed/loaded** → `.svelte` treated as unparseable/skipped → exit 0 on never-formatted files. Verify `.svelte` in scope + plugin resolves (else exit 2).
- **Plugin ordering** — `prettier-plugin-tailwindcss` last; svelte before it. Wrong order → class sorting silently doesn't run while `--check` passes.
- **Prettier ↔ ESLint conflict** — use **`eslint-config-prettier`** (turns off conflicting ESLint stylistic rules); in flat config it must be **last** (`eslint-config-prettier/flat`). Don't run formatting *through* ESLint (`eslint-plugin-prettier`) in a scoring linter — run Prettier directly.
- **`.prettierignore` scope** — excluded files pass trivially; confirm intended files were in scope.

**Sources:** <https://prettier.io/docs/cli> · <https://github.com/sveltejs/prettier-plugin-svelte> · <https://github.com/prettier/eslint-config-prettier> · <https://github.com/tailwindlabs/prettier-plugin-tailwindcss>

---

## DIMENSION 12 — Svelte practices

### De-facto: svelte-check (a11y + compiler) + eslint-plugin-svelte (runes/best-practice)
```bash
npx sv check --output machine --tsconfig ./tsconfig.json   # a11y + types, space-separated rows
npx sv check --output machine-verbose                       # NDJSON
npx eslint . --format json -o eslint-report.json            # svelte/* rules
```
`--output machine` rows: `<ts> ERROR|WARNING "file.svelte" L:C "msg"` + `<ts> COMPLETED N FILES X ERRORS Y WARNINGS Z FILES_WITH_PROBLEMS`. **Score off the COMPLETED line + classify WARNING rows by `a11y_*` prefix.** Useful flags: `--threshold error|warning`, `--compiler-warnings "code:error,code:ignore"` (promote a11y to hard error).

### a11y is COMPILER-driven (key Svelte trait)
Svelte has **no jsx-a11y-equivalent ESLint plugin** — the **compiler emits `a11y_*` warnings** (Svelte 5 snake_case: `a11y_missing_attribute`, `a11y_img_redundant_alt`, `a11y_positive_tabindex`, `a11y_no_redundant_roles`, `a11y_autofocus`, `a11y_unknown_role`…; Svelte 4 used hyphenated `a11y-*`). Surfaced by svelte-check **and** `svelte/valid-compile` in ESLint.

### eslint-plugin-svelte rules (flat-config only, `svelteConfig` in parserOptions)
- **Security/XSS:** `svelte/no-at-html-tags` ★ (disallow `{@html}`), `svelte/no-target-blank`.
- **Correctness:** `svelte/require-each-key` ★ (≈ React `jsx-key`), `svelte/no-dom-manipulating` ★, `svelte/no-store-async` ★, `svelte/no-reactive-reassign` ★, `svelte/no-unused-svelte-ignore` ★, `svelte/valid-compile`, `svelte/button-has-type`.
- **Svelte 5 runes hygiene:** `svelte/prefer-svelte-reactivity` ★, `svelte/no-unnecessary-state-wrap` ★, `svelte/prefer-writable-derived` ★ (writable `$derived` over `$state`+`$effect`), `svelte/no-immutable-reactive-statements` ★, `svelte/prefer-derived-over-derived-by`.

### Legacy `$:` / runes migration + heavy-logic detection
- No single dedicated "ban `$:`" rule. Detect legacy by (a) running in **runes mode** (Svelte 5 `runes: true`) where `$:` becomes a compiler error via `svelte/valid-compile`/svelte-check, or (b) a custom AST rule flagging `$:` labels + `export let` (legacy props).
- **Heavy logic in components:** no built-in metric — compute per-`.svelte` script-block size + cyclomatic complexity (ESLint `complexity`/`max-lines` run on the `<script>` block when the svelte parser is active); flag > ~150 lines or cc > 10, recommend extraction to `$lib`.

### FALSE-GREEN pitfalls
- **a11y warnings are warnings, not errors** (dominant false green) — a component riddled with `a11y_*` passes with exit 0 by default. **Explicitly count `a11y_*` WARNING rows** or promote via `--compiler-warnings`/`warningFilter`.
- **Runes rules only fire in Svelte 5 / runes mode** — no-ops on Svelte 4 or legacy-mode components → false green on "modern Svelte." Confirm `compilerOptions.runes` / `<svelte:options runes />`.
- **`svelte/valid-compile` needs the compiler + right `svelte.config.js`** — misconfigured `svelteConfig` makes svelte rules under-report.
- **svelte-check skips files outside `--tsconfig` / unresolved aliases** — run after `svelte-kit sync`.
- **`{@html}` flagged but disabled inline** via `<!-- svelte-ignore -->` → real XSS hidden. Pair with `svelte/no-unused-svelte-ignore`; audit suppression comments.

**Sources:** <https://svelte.dev/docs/cli/sv-check> · <https://svelte.dev/docs/accessibility-warnings> · <https://svelte.dev/docs/svelte/compiler-warnings> · <https://sveltejs.github.io/eslint-plugin-svelte/> · <https://github.com/sveltejs/eslint-plugin-svelte/blob/main/docs/rules.md> · <https://svelte.dev/blog/runes> · <https://geoffrich.net/posts/svelte-a11y-limits/>

---

## CRUCIAL SECTION — Delta React vs Svelte (layered linter design)

> **The architectural asymmetry to encode:** React pushes UI-correctness into **ESLint plugins** (more plugins, ONE type CLI — `tsc` covers `.tsx` natively). Svelte pushes them into the **compiler** (FEWER ESLint rules, but a SECOND diagnostic CLI — `svelte-check` — because `tsc` cannot read `.svelte`). A naive "just swap the ESLint preset" design misses the `svelte-check` requirement and the absence of any hooks/refresh/a11y-plugin analogue in Svelte.

### Layer 1 — NODE COMMON BASE (framework-agnostic, ~80% of rules)
Applies identically to any TS/Node project. Both UI profiles inherit it; deltas are **additive, never replacing**.

| Tool / Plugin | Catches |
|---|---|
| ESLint core (`no-unused-vars`, `no-undef`, `complexity`, `eqeqeq`, `no-debugger`) | Dead code, undeclared vars, cyclomatic complexity, footguns |
| typescript-eslint (`recommended`→`strict-type-checked`, `stylistic`) | Type-aware bugs (`no-floating-promises`, `no-misused-promises`, `no-explicit-any`, `no-unnecessary-condition`) — **the heart of the base** |
| eslint-plugin-sonarjs (`cognitive-complexity`, `no-identical-functions`, `no-duplicate-string`) | Cognitive complexity, duplicated logic, code smells |
| eslint-plugin-import / import-x (`no-cycle`, `no-unresolved`, `order`) | Import cycles, phantom deps, ordering |
| eslint-plugin-security | Insecure JS patterns (eval, object injection, unsafe regex) |
| Prettier + eslint-config-prettier | Formatting (kept out of ESLint scope) |
| `tsc --noEmit` | Type errors (`.tsx` natively) |
| Vitest / Playwright | Test correctness |
| knip | Unused files/exports/deps |
| madge / dependency-cruiser | Circular deps / architecture policy |
| jscpd | Copy-paste duplication |
| npm / pnpm audit | Dependency CVEs |
| gitleaks | Secret detection |

### Layer 2 — DELTA REACT (four ESLint plugins; NO second CLI)
| Rule / Plugin | Why it exists / catches |
|---|---|
| **`react-hooks/rules-of-hooks`** | Hooks identified by **call order**; conditional/looped calls corrupt React's state bookkeeping. NO Svelte equivalent (Svelte reactivity is compiler-driven, not hook-driven). |
| **`react-hooks/exhaustive-deps`** | Missing effect deps → **stale closures** (effect captures old value, never re-runs). NO Svelte equivalent (deps tracked at compile time). Configurable `additionalHooks`. |
| `react-hooks/*` **compiler rules** (v6+/React 19): `purity`, `set-state-in-render`, `set-state-in-effect`, `immutability`, `refs`, `preserve-manual-memoization`, `static-components`… | Enforce purity/immutability the React Compiler needs to auto-memoize safely. (`eslint-plugin-react-compiler` was MERGED into `eslint-plugin-react-hooks` v6 under `react-hooks/*`; presets slimmed to `recommended` + `recommended-latest`.) |
| eslint-plugin-react: `react/jsx-key`, `react/no-array-index-key`, `react/jsx-no-target-blank`, `no-danger-with-children`, `no-unescaped-entities`, `display-name` | JSX/component correctness + JSX security |
| **eslint-plugin-jsx-a11y** (`alt-text`, `anchor-is-valid`, `aria-props`, `label-has-associated-control`, `click-events-have-key-events`) | **JSX accessibility — a SEPARATE plugin** (React's a11y home). In Svelte this is the COMPILER's job. |
| **eslint-plugin-react-refresh** (`only-export-components`) | Files mixing components with non-component exports break the Fast-Refresh/HMR boundary. NO Svelte equivalent (Svelte HMR boundaries are compile-time). |

```js
// React flat config 2025–2026
export default tseslint.config(
  js.configs.recommended,
  tseslint.configs.strictTypeChecked,
  react.configs.flat.recommended,
  reactHooks.configs.flat.recommended,   // rules-of-hooks + exhaustive-deps + compiler rules
  jsxA11y.flatConfigs.recommended,
  reactRefresh.configs.vite(),
);
```

### Layer 3 — DELTA SVELTE (one ESLint plugin + one extra diagnostic CLI)
| Rule / Tool | Catches |
|---|---|
| eslint-plugin-svelte reactivity (`no-reactive-functions`, `no-reactive-literals`, `no-dom-manipulating`) | Svelte reactivity misuse |
| `svelte/require-each-key` | Missing `key` in `{#each}` (≈ React `jsx-key`) |
| `svelte/valid-compile` | Svelte compiler warnings (incl. a11y codes) escalated to lint errors |
| `svelte/prefer-svelte-reactivity`, `prefer-writable-derived`, `prefer-derived-over-derived-by`, `no-unnecessary-state-wrap` | Svelte 5 runes best-practices |
| `svelte/no-at-html-tags`, `no-target-blank` | XSS / unsafe links |
| **`svelte-check` CLI** | `.svelte` type-checking + compiler **a11y** + unused CSS — the second diagnostic pass `tsc` cannot do. **No React equivalent.** |

### Layer 4 — Concern-by-concern asymmetry (the table that drives the design)
| Concern | React | Svelte | Linter implication |
|---|---|---|---|
| **a11y** | separate ESLint plugin (jsx-a11y) | **compiler** (`a11y_*`) via svelte-check + `svelte/valid-compile` | a11y = react-delta *ESLint rules* vs svelte-delta *compiler/CLI* — NOT symmetric |
| **Reactivity correctness** | react-hooks (`rules-of-hooks`, `exhaustive-deps`) | compiler + eslint-plugin-svelte; **no `exhaustive-deps`/`rules-of-hooks` analogue** | hooks rules are react-only |
| **Type-checking UI files** | `tsc` covers `.tsx` (base suffices) | needs **`svelte-check`** (2nd CLI) | svelte-delta adds a CLI; no react-delta CLI |
| **HMR boundary** | eslint-plugin-react-refresh | compiler (no rule) | react-only |
| **List/key correctness** | `react/jsx-key`, `no-array-index-key` | `svelte/require-each-key` | symmetric concept, different plugin |

### Recommended layered architecture
1. **`node-base`** (always applied): ESLint core + typescript-eslint strict-type-checked + sonarjs + import(-x) + security + prettier-config + companion CLIs (`tsc`, vitest, knip, madge/dependency-cruiser, jscpd, npm audit, gitleaks). ~80% of rules, identical for both frameworks.
2. **`react-delta`** (additive): eslint-plugin-react + react-hooks (+ compiler rules) + jsx-a11y + react-refresh. No extra CLI.
3. **`svelte-delta`** (additive): eslint-plugin-svelte (+ runes rules) **AND** an extra `svelte-check` CLI pass (a11y + Svelte type-checking the base `tsc` can't do).

> **Freshness caveat.** React Compiler rule names + the two-preset consolidation (`recommended`/`recommended-latest`) reflect `eslint-plugin-react-hooks` v6 / React Compiler v1.0 (late 2025). If you pin versions, verify the exact `react-hooks/*` rule list against the installed plugin — the compiler rule set is still expanding release-to-release.

**Sources:** <https://github.com/facebook/react/blob/main/packages/eslint-plugin-react-hooks/README.md> · <https://react.dev/reference/eslint-plugin-react-hooks> · <https://react.dev/blog/2025/10/07/react-compiler-1> · <https://github.com/jsx-eslint/eslint-plugin-react> · <https://github.com/jsx-eslint/eslint-plugin-jsx-a11y> · <https://github.com/ArnaudBarre/eslint-plugin-react-refresh> · <https://github.com/sveltejs/eslint-plugin-svelte> · <https://github.com/sveltejs/language-tools/tree/master/packages/svelte-check> · <https://typescript-eslint.io/users/configs/>

---

## Appendix — scoring cheat-sheet

| Dimension | Command (machine output) | Verdict source | Score detail | Hard-fail extras |
|---|---|---|---|---|
| Lint | `eslint . --format json` | exit `0`/`1`/`2` | `sum(errorCount)`, `sum(warningCount)` | exit `2` = config error; `[]` = nothing linted |
| Type (TS) | `tsc --noEmit --pretty false` (`tsc -b` if refs) | exit code | `grep -c ': error TS'` + `Found N` | `--listFiles` to detect skipped files; crash = fail |
| Type (Svelte) | `svelte-check --output machine-verbose --tsconfig <app>` | exit + `COMPLETED…ERRORS WARNINGS` | NDJSON records (TS `code`) | wrong tsconfig / no `svelte-kit sync` |
| Complexity | `eslint . --format json` | `severity==2` | `ruleId in {complexity, sonarjs/cognitive-complexity}` | rule OFF by default; default max=20 |
| Sec (deps) | `npm/pnpm audit --json` | exit / count | `metadata.vulnerabilities.{high,critical}` | npm gate vs pnpm filter; `--omit=dev` hides build vulns |
| Sec (code) | `eslint . --format json` | warning (heuristic) | `ruleId ^security/detect-` | high FP — advisory not gate |
| Secrets | `gitleaks dir . --report-format json --exit-code 1` | exit `1` | finding count | trufflehog needs `--fail` |
| Deps | `knip --reporter json --no-exit-code` | parse JSON | `issues[].{dependencies,unlisted,unresolved}` | exit 2 = tool error |
| Tests | `vitest run --reporter=json` | `success` | `numFailedTests`; **assert `numTotalTests>0`** | `passWithNoTests` false green |
| Coverage | `vitest run --coverage --coverage.reporter=json-summary` | — | `total.*.pct` ≥ 80 | `coverage.all` off / `autoUpdate:true` |
| Architecture | `madge --circular --json` / `depcruise --output-type json` | `len()==0` / `summary.error` | cycle list / violations[] | missing `--ts-config` → false clean |
| Dead code | `knip --exports --reporter json` | parse JSON | `issues[].{files,exports,types,duplicates}` | entry-point config; exit 2 |
| Manifest | read `package.json`/`tsconfig.json`; `publint --json` | assertions | required fields, `strict:true` | exports overrides main; resolve `extends` |
| Duplication | `jscpd --reporters json` | `statistics.total.percentage` < 3–5% | duplicates[] | generated code; threshold tuning |
| Formatting | `prettier --list-different .` | exit `0`/`1`/`2` | filenames differ | exit 2 = crash; plugin not loaded |
| Svelte practices | `svelte-check --output machine` + `eslint . --format json` | `COMPLETED` line + `severity` | `a11y_*` rows + `svelte/*` ruleIds | a11y = warning by default |
