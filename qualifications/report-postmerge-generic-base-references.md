# Références génériques — qualification ROOT après fusion

Fusion dans `dev` : `6c6926290c29660e600c1f20890669fcd3e98e66`.
Candidat : `c3f1e5e`, base `93845a0`, contre-audit indépendant favorable.

Le correctif de trois lignes reconnaît les références réellement évaluées
dans un nœud tree-sitter `subscript`, via son champ `value`. Aucune exemption,
aucun export privé artificiel, aucun seuil et aucun parser de texte ajoutés.
La régression causale conserve les classes véritablement inutilisées.

## Mesure ROOT sur dev

MCP `audit_test`, package `axm-ast`, suite entière, résultats par cas :
**1702 PASS, 1 SKIP, 1703 collectés**, 55,5 secondes. Le skip historique est
`test_workspace_packages_no_regression[axm-engine]` : le package voisin
`axm-nexus/packages/axm-engine` n'existe pas sur disque. Cette interopérabilité
n'est pas annoncée qualifiée.

Couverture limitée à `src/axm_ast`, branches activées, selon la configuration
inchangée : **90,4 % combinés** ; XML : 6899/7471 lignes (92,34 %) et
2440/2856 branches (85,43 %). Aucun taux de branches de 90 % revendiqué.

MCP `audit(category="lint")` sur le package fusionné : **100**, quatre
contrôles PASS. Preflight Forge propre après ces mesures. Les qualifications
candidates et leurs onze cas audit distincts restent dans
`generic-base-references.md` ; ils ne sont pas présentés comme relancés par ROOT.

## Fournisseur vivant et fournisseur neuf

La suite fusionnée contient les deux preuves en interpréteur neuf du vrai
fournisseur, avec chemin de source attesté. Le candidat avait également
qualifié le gate Fit du moteur général : aucun symbole mort, score 100,
fournisseur neuf attesté dans l'artefact de diagnostic décrit par son rapport.

Après fusion, ROOT a aussi répété le même appel MCP public sur le dossier
generic original : **quatre symboles morts sont encore signalés**, dont la
base réellement utilisée. Le serveur actif garde donc l'ancien code en
mémoire. Cette mesure rouge n'est pas transformée en verte par la fusion ;
aucun redémarrage, patch du serveur ni actualisation du catalogue revendiqués.
Le nouveau code est qualifié, son chargement dans ce serveur reste à effectuer.

La méthode `falsify-investigate` a imposé le contraste minimal avant correction
et la distinction entre ces fournisseurs. Aucun runtime ML ni Ray lancé.
