# `framework=` — étendre axm-init et axm-audit à Node/Svelte

> Branche worktree : `feat/node-svelte-support`. Aucun changement sur `main`.
> Principe directeur : **on ne crée pas de nouveaux outils**. On ajoute une
> dimension `framework` (défaut `python`, nouvelles valeurs `node` et `svelte`,
> `svelte` héritant de `node`). On porte l'**intention** de chaque règle/check
> Python vers son équivalent d'écosystème Node, pas l'outil.

## 1. Invariant de non-régression

Tout l'existant Python doit continuer à fonctionner à l'identique :

- chaque règle audit et chaque check init garde `framework="python"` par défaut ;
- quand aucun `framework=` n'est passé, il est **auto-détecté** à partir des
  marqueurs du projet, et un projet Python est détecté comme `python` ;
- les signatures MCP/CLI existantes ne changent pas (ajout d'un paramètre
  optionnel `framework` uniquement).

## 2. Détection de framework (partagée)

`detect_framework(path) -> Framework` (enum `python | node | svelte`) :

| Marqueur trouvé | Résultat |
|---|---|
| `pyproject.toml` (et pas de `package.json` au même niveau) | `python` |
| `package.json` avec dép/devDep `svelte` **ou** `svelte.config.js` présent | `svelte` |
| `package.json` sans marqueur Svelte | `node` |
| rien de tout ça | `python` (défaut conservateur) |

Override explicite : le paramètre `framework=` passé à l'outil court-circuite la
détection. `svelte` hérite de `node` (un projet svelte fait tourner les règles
`node` **plus** les règles `svelte`-spécifiques).

## 3. axm-audit — point d'injection

- Aujourd'hui : `@register_rule(category)` remplit `_RULE_REGISTRY[category]`,
  et `get_rules_for_category(category)` instancie ces classes.
- Extension : `@register_rule(category, framework="python")` → le registry
  devient indexé `(category, framework)` ; `get_rules_for_category(category,
  framework=...)` ne renvoie que les règles du framework demandé (avec héritage
  node→svelte). `audit_project()` / `AuditTool.execute()` acceptent un
  `framework` optionnel, sinon `detect_framework(project_path)`.
- Les règles Python existantes ne changent pas : `framework` par défaut =
  `python` dans le décorateur.

## 4. axm-init — point d'injection

### Scaffold (templates)
- `TemplateType` reste {standalone, workspace, member} ; on ajoute une
  dimension `framework`. `get_template_path(template_type, framework)` choisit le
  bon dossier Copier (`templates/node-project`, `templates/svelte-project`, …).
- `InitScaffoldTool.execute()` accepte `framework=` (défaut python).

### init_check (gold standard)
- Aujourd'hui : `_discover_checks()` scanne les modules de `axm_init.checks` ;
  le nom de module = catégorie ; toutes les fns `check_*` publiques sont prises.
- Extension : checks rangés par framework (sous-package
  `axm_init.checks.node.*`, `axm_init.checks.svelte.*`, l'existant restant le jeu
  `python`). `CheckEngine(project_path, framework=...)` choisit le jeu de checks ;
  `framework` auto-détecté si non fourni.

## 5. Mapping d'intention (résumé — détail dans AUDIT_RULE_MAPPING.md)

| Catégorie | Intention conservée | Outil Python | Outil Node/Svelte |
|---|---|---|---|
| lint | style + bugs + simplifs | ruff | ESLint (typescript-eslint, eslint-plugin-svelte) |
| type | typage statique | mypy | tsc --noEmit (+ svelte-check) |
| complexity | cc<10 / cog<15 | ruff C901 + complexipy | ESLint `complexity` + sonarjs cognitive |
| security | secrets + vulnérabilités | bandit + regex | eslint-plugin-security + `npm audit` (+ regex réutilisée) |
| deps | pins + inutilisées + vulns | deptry + pip-audit | depcheck + `npm audit` |
| testing | suite verte + couverture | pytest + coverage | vitest run + c8/istanbul |
| test_quality | pyramide, dup, tautologie, naming | AST python | AST TS (mêmes invariants, fichiers `*.test.ts`) |
| architecture | pas de cycle, couplage, god class | imports python | madge / dependency-cruiser |
| structure | manifest complet + layout | pyproject.toml | package.json + tsconfig + svelte.config |
| practices | bare except, blocking io, docstrings, mirror | AST python | no empty catch, no sync fs en async, TSDoc, test-mirror |

## 6. Plan de prototypage (ordre)

1. `detect_framework` partagé (dans `axm-ingot` ou helper local par package).
2. axm-audit : registry `(category, framework)` + filtrage + 1 règle node POC
   (lint ESLint) prouvant la chaîne de bout en bout.
3. axm-init : `framework` dans `CheckEngine` + 1 jeu de checks node POC
   (`package.json` completeness) + 1 template `node-project` minimal.
4. Tests unit + e2e ; audit_test ; commit sur la branche worktree.

## 7. Résultats du POC (livré sur `feat/node-svelte-support`)

Mécanisme `framework=` câblé de bout en bout dans **axm-audit** et **axm-init**,
100% rétro-compatible (défaut `python`, auto-détection sinon).

**axm-audit**
- `core/framework.py` : `Framework` (python/node/svelte), `detect_framework`,
  `resolve_frameworks` (svelte → node+svelte).
- Registry `@register_rule(category, framework=…)` keyé `(category, framework)` ;
  `get_registry()` reste la vue python (back-compat), `get_registry_for(fw)` est
  le nouvel accès ; `auditor` filtre via `_merged_registry` + auto-détection.
- Règle POC `NodeLintRule` (catégorie `lint`, framework `node`) → ESLint JSON,
  même `rule_id=QUALITY_LINT`, même scoring `100 - issues*2`.
- **Prouvé e2e sur un vrai projet ESLint** : 3 issues réelles → score 94,
  `passed=False`. Faux-vert (npx non-install) attrapé et corrigé : un outil non
  installé localement = `ERROR` non-vert.

**axm-init**
- `core/framework.py` (miroir), `CheckEngine(framework=…)` + `CHECKS_BY_FRAMEWORK`.
- Jeu de checks `checks/node/package_json.py` (existence + métadonnées).
- Template Copier `templates/node-project` + `get_template_path(type, framework)` ;
  `InitScaffoldTool` accepte `framework=`.
- **Boucle prouvée** : `scaffold framework=node` → `init_check` auto-détecte node
  → score 100/A.

**Validation** : axm-audit 2010 tests verts (lint A 99.8 / type 100) ;
axm-init 707 tests verts (lint A 99.8 / type 100). 28 nouveaux tests ; 9 tests
existants adaptés à l'API framework-aware (aucune régression fonctionnelle).

## 8. Architecture en couches (react-ready)

Le découpage `python | node | svelte` initial était trop grossier. Modèle final
**en couches**, piloté par `resolve_frameworks` :

- **`node`** = socle commun JS/TS (ESLint, tsc, prettier, vitest, knip, madge,
  jscpd, npm audit, gitleaks). Réutilisé tel quel par tous.
- **`svelte`** = `node` + delta `.svelte` (svelte-check : type + a11y que `tsc`
  ne couvre pas). `resolve_frameworks(svelte) → (node, svelte)`.
- **`react`** = `node` + delta `.jsx/.tsx` (eslint-plugin-react-hooks,
  jsx-a11y, react-refresh). `resolve_frameworks(react) → (node, react)`.

Ajouter un framework UI (vue, solid…) = 1 membre d'enum + 1 entrée dans
`_NODE_UI_FRAMEWORKS` + un sous-package `rules/<fw>/` (audit) / `checks/<fw>/`
(init). **Aucun refactor.** React est déjà câblé (enum + détection + résolution
+ `_FRAMEWORK_CHECK_PACKAGES`) ; seul son delta de règles reste à écrire.

## 9. État livré (node base + svelte delta)

**axm-audit — 16 règles node déclarées (12 implémentées + 4 placeholders) :**

| Catégorie | Règles implémentées | Outil |
|---|---|---|
| lint | QUALITY_LINT, QUALITY_FORMAT, QUALITY_DEAD_CODE | ESLint, Prettier, knip |
| type | QUALITY_TYPE | tsc |
| complexity | QUALITY_COMPLEXITY | ESLint + sonarjs |
| deps | DEPS_HYGIENE, DEPS_AUDIT | knip, npm audit |
| security | PRACTICE_SECURITY | gitleaks |
| testing | QUALITY_TESTING | vitest |
| architecture | ARCH_CIRCULAR, ARCH_DUPLICATION | madge, jscpd |
| structure | STRUCTURE_PACKAGE_JSON | (lecture package.json+tsconfig) |
| test_quality | **NON IMPLÉMENTÉ** (4 placeholders) | requiert AST TS |

Delta **svelte** : `SVELTE_CHECK` (type+a11y). → svelte = 13 règles, react = 12
(node) en attendant son delta.

**axm-init — 6 checks node + 1 delta svelte :** package_json (×2), tsconfig
(exists+strict), tooling (eslint config + test script) ; delta svelte =
svelte.config. Templates `node-project` (enrichi) et `svelte-project` (nouveau)
qui passent leurs propres checks ET les règles audit out-of-the-box.

**Doctrine appliquée partout** (issue de la recherche) : *exit code = verdict,
JSON = détail*. Un outil non installé localement → `ERROR` non-vert (jamais de
faux-vert). `findings_returncodes` gère les outils qui surchargent un exit non-nul
pour signaler des findings (tsc=2, npm audit=1, vitest=1, prettier=1).

**Validé e2e sur projets réels** : audit node sur un projet à 7 outils installés
(madge/knip/eslint+sonarjs/tsc/prettier/vitest/npm-audit) → chaque règle score de
vraies findings ; jscpd+gitleaks absents → fail loud. init scaffold→check node ET
svelte → 100/A.

## 10. La question de l'AST TS (décision)

Deux familles de règles :
- **Famille 1 (déléguées à un outil externe)** — lint, type, complexity, format,
  deps, dead_code, security, testing, architecture, duplication. L'AST est fait
  par l'outil node ; axm-audit score le JSON. **Ne touche pas axm-ast.** → toutes
  implémentées.
- **Famille 2 (analyse AST propre en Python)** — les invariants `test_quality`
  spécifiques AXM (mirror, pyramid, tautology, duplicate). En Python elles
  utilisent le tree-sitter d'axm-ast. **Pas d'outil node équivalent** → il faut un
  AST TS côté Python (étendre axm-ast avec tree-sitter-typescript, ou un helper
  ts-morph en subprocess). **Décision différée** : ces 4 règles sont déclarées
  comme placeholders `NOT_IMPLEMENTED` (score=None, jamais de faux-vert) qui
  nomment explicitement la dépendance manquante.

## 11. Reste à faire

1. **Delta react** : eslint-plugin-react-hooks (rules-of-hooks, exhaustive-deps),
   jsx-a11y, react-refresh — sous `rules/react/` (le câblage est déjà prêt).
2. **AST TS** : trancher famille 2 (axm-ast tree-sitter-typescript vs ts-morph)
   pour implémenter les 4 placeholders test_quality.
3. **Factoriser `framework.py`** dans `axm-ingot` (actuellement dupliqué
   audit/init).
4. **Exposer `framework=`** dans les signatures MCP/CLI des tools `audit`/`init_*`.
