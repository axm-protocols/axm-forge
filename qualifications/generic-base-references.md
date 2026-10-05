# Références des bases génériques — 5 octobre 2026

Base Forge : `93845a0`. Aucun changement Learning/Fit, aucune exemption,
aucun seuil modifié, aucun redémarrage du serveur MCP.

## Cause et correction

L'expérience initiale `/tmp/axm-dead-code-pair.EXU2HD/01-repro.md`
change uniquement `Child(_Base)` en `Child(_Base[int])` : le serveur MCP
signale respectivement deux et quatre symboles morts, deux répétitions.

La régression publique `analyze_package` → `find_dead_code` reproduit
2 PASS / 2 FAIL avant correction : simple et qualifié passent ; générique
et générique qualifié signalent à tort `_Base` et `_Base.inherited`.

`core.callers._extract_ref_name` reconnaît désormais un nœud tree-sitter
`subscript` en inspectant récursivement son champ `value`. Trois lignes
exécutables, sans parsing du texte ni modification de `dead_code.py`.
Les identifiants et attributs gardent leur contrat. Les références génériques
comme arguments, éléments de conteneur et valeurs retournées sont couvertes.
Le comportement reste syntaxique et par nom : aucune résolution de type,
d'alias ou de portée n'est ajoutée.

## Qualification

- Régression des bases : 4/4 PASS après correction, avec base et méthode
  héritée vivantes ; `_Unused` et `Child` restent morts dans chaque variante.
- Suite complète axm-ast finale : 1702 PASS, 1 SKIP, 1703 collectés, 35,1 s.
  Skip existant : package voisin absent
  `/Users/gabriel/Documents/Code/python/axm-workspaces/axm-nexus/packages/axm-engine`.
  Cette absence n'est pas qualifiée comme une réussite d'interopérabilité.
- Lot ciblé AST et règles audit dead-code : 18/18 PASS, 1,0 s.
  Il recouvre sept cas de la suite AST et contient onze cas audit ; ces comptes
  ne sont pas additionnés à la suite complète comme des tests distincts.
- Lint et type axm-ast : 100. Test-quality : 95,8, exactement les cinq imports
  privés préexistants également mesurés sur Forge principal, aucun ajout.
- Deux preuves subprocess attestent le chemin du fournisseur dans ce checkout
  et obtiennent exactement `Child`, `_Unused` pour simple et générique.

Les fichiers originaux plain/generic de l'expérience sont inchangés.
`audit_test` sur `/tmp/axm-dead-code-pair.EXU2HD/test_candidate_pair.py`
les requalifie dans un nouveau processus : 2/2 PASS, fournisseur attesté.
Un troisième diagnostic sur Fit program-engine via `DeadCodeRule.check`
donne PASS, score 100, `dead_count=0`, `symbols=[]` ; artefact mesuré
`/tmp/axm-dead-code-pair.EXU2HD/fit-fresh-gate.json` avec chemin fournisseur.
Ces diagnostics temporaires ne deviennent pas des tests portables du dépôt.

Le serveur MCP actif garde son ancienne version en mémoire : le même dossier
generic y produit encore quatre symboles morts. La qualification du checkout
ne signifie donc pas que le catalogue vivant a été actualisé. Un chargement
ultérieur de la version corrigée sera nécessaire, sous contrôle du parent.
