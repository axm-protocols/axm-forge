# Lecture des dépendances des agents exec

## Mesure DEV-55

Run observé : `dev.work.exec/20260930/222938_b9a32fe5`, nœud
`implement`, tentatives 0 et 1 (indexation lens).
Les deux tentatives ne modifient aucun fichier. Les appels AST restent limités
au package axm-cron ; `axm.tools.node` n'est pas résolu. Le lecteur refuse la
source externe avec `read_file | ESCAPE | Path escapes project root`.
Le prompt demande un arrêt au premier défaut d'environnement. Le bilan est
`product_quality`, avec des preuves contre implement et sans faute instrument.
La relation à DEV-57 est un constat opérateur, non réémise pour cette enquête.

Nuance C3 : la résolution MCP refuse les échappements relatifs et certains
échappements par lien symbolique ; ce n'est pas un refus universel de tous
les chemins absolus. Le lecteur possède en plus son propre garde-fou strict.

## Contrat et résolution

Le contrat transporte l'interpréteur des tests, le package de départ et les
chemins Python de la lane. Le SDK interroge les métadonnées avec cet interpréteur
isolé, suit les exigences actives (marqueurs et extras transitifs), puis autorise
uniquement les racines d'import des distributions déclarées : sources éditables
ou fichiers enregistrés dans site-packages. Il n'autorise jamais le dossier
site-packages entier, ni un dépôt frère entier.

La décision du contrat, les wrappers MCP, read_file et les outils AST emploient
la même résolution. Le contexte est attaché à chaque invocation, sans variable
globale partagée entre sessions. Les chemins réels interdisent les liens
symboliques sortants ; le cache AST non cloisonné n'est pas utilisé en session.
La résolution des modules et réexportations statiques ne charge pas leur code.

Les écritures gardent exactement execution_root et les préfixes C3 existants.
Une dépendance autorisée en lecture n'ajoute aucun préfixe d'écriture.

## Brief et verdict

Les références externes des symboles, critères et imports des témoins donnent
des signatures et docstrings entières, avec chemin et digest. Ce contenu est
obligatoire dans le budget C1. Si la fenêtre effective ne suffit pas, le brief
échoue explicitement comme instrument ; aucune troncature silencieuse.

Le prompt propose une route de lecture déclarée avant de conclure au blocage.
Le backend classe les refus à partir des appels d'outils mesurés : une
réussite ultérieure sur la même source résout le défaut ; un symbole inexistant
ou un chemin arbitraire ne devient pas une faute instrument.
Un refus non résolu conserve outil, arguments, source et raison, et produit un
constat terminal sans cible producteur : Non exécuté ⚑ (instrument).
Le warden construit alors une réparation tooling, pas une amélioration green.

## Rejeu réel, strictement en lecture

`dev55-dependency-context.json` conserve le contexte de la lane observée.
`dev55-dependency-replay.json` conserve le résultat des wrappers MCP réels :
inspection du module et de load_tool, lecture de sa source, écriture refusée
hors surface. Le test compare aussi le hash du fichier avant et après.

```sh
BASE=/Users/gabriel/Documents/Code/python/axm-tribunal-wt
PYTHONDONTWRITEBYTECODE=1 \
AXM_DEPENDENCY_REPLAY_CONTEXT=$BASE/axm-forge-deps/audits/dev55-dependency-context.json \
AXM_DEPENDENCY_REPLAY_REPORT=$BASE/axm-forge-deps/audits/dev55-dependency-replay.json \
PATH=$BASE/axm-forge-deps/.venv/bin:$PATH \
$BASE/axm-forge-deps/.venv/bin/axm audit_test \
  --path $BASE/axm-forge-deps \
  --files '["packages/axm-mcp/tests_axm_mcp/e2e/test_dependency_replay.py"]'
```

Les suites complètes utilisent chaque venv dédié, son bin absolu sur PATH,
et `PYTHONDONTWRITEBYTECODE=1`. Les deux tests d'extraction F401 de axm-edit
échouent également sur l'archive de HEAD avant correctif, avec le même Ruff :
ils ne sont pas corrigés dans cette branche.

Validation complète :
- Forge SDK/AST/MCP/edit : 2885 réussites, deux échecs F401 préexistants,
  trois skips ; les sept nouvelles régressions passent.
- Nexus dag/tribunal : 2850 réussites, deux skips.
- Protocols core/dev : 1186 réussites, deux échecs d'ordre préexistants.
  Les deux tests de graphes publiés passent seuls ; les unités core/dev suivies
  de ces tests échouent aussi sur les archives HEAD (902 réussites, deux échecs).
  La nouvelle preuve d'API, puis ces deux tests, passent ensemble.
- Warden : 982 réussites unitaires ; 536 d'intégration et deux skips ;
  27 e2e. Types passent avec harness consulté en lecture seule via PYTHONPATH,
  sans build éditable du checkout cortex.
- Types, lint et format passent sur tous les packages concernés ; les
  changements provisoires de configuration uv ne font pas partie des commits.

Ordre de fusion recommandé : Forge, Nexus, Protocols, Hub (test uniquement).
Après installation coordonnée dans le runtime opérateur et son MCP, remettre
le ticket existant DEV-55 en backlog par ticket_update, conserver ses liens,
ses oracles et sa surface. Le warden reconstruira brief et contrats avec la
résolution de la nouvelle lane ; ne pas relancer manuellement le graph.
L'ancienne tentative terminée n'est pas modifiée. Aucune relance opérationnelle
ni mutation du store partagé n'est faite par ce correctif.
