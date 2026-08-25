# doc_impact — la portée du signal

`ast_doc_impact` (`analyze_doc_impact`) répond à une question lexicale : où le
nom d'un symbole apparaît-il dans la documentation ? Il ne répond jamais à la
question sémantique : ce qui est écrit à propos de ce symbole est-il encore
vrai ? Cette page énonce les conséquences de cet écart et la règle de lecture
qui en découle. La formulation canonique vit dans la docstring de
`analyze_doc_impact` ; cette page la reprend, elle ne la concurrence pas.

À ne pas confondre avec `ast_impact`, le rayon d'impact **du code** (appelants,
modules affectés, tests à rejouer), décrit dans
[Analyze Change Impact](../howto/impact.md) : la présente page ne parle que du
signal **documentaire**.

## Limites — ce que cet outil ne détecte pas

Les trois signaux (`doc_refs`, `undocumented`, `stale_signatures`) reposent sur
un appariement **purement lexical**, jamais sémantique. Un symbole compte comme
mentionné dès que son nom nu apparaît entre backticks ou dans un titre
Markdown, et une signature documentée n'est comparée qu'à l'intérieur d'un bloc
de code délimité. Aucun sens n'est lu. Trois conséquences :

1. **Une sémantique changée à nom inchangé passe inaperçue.** Réécrivez ce que
   fait un symbole sans toucher à son nom : la sortie de l'outil reste
   **inchangée**, octet pour octet. La prose qui ment désormais n'est signalée
   par rien.
2. **Un simple name-drop est compté comme de la documentation.** Une seule
   mention entre backticks, même dans une phrase sans rapport, suffit à retirer
   le symbole de `undocumented`. La présence n'est pas la couverture.
3. **`undocumented` n'est pas un oracle de non-régression.** Un résultat vide ou
   identique au précédent ne prouve aucune absence de dérive documentaire. Lisez
   `doc_refs` comme une liste de pages à relire, jamais comme une preuve que la
   documentation est correcte ou à jour.

### La règle : quand la sémantique change sans que le nom bouge

Quand la sémantique d'un symbole change sans que son nom bouge, l'outil ne dira
rien : relisez **chaque page** listée dans `doc_refs` **à la main**, et corrigez
sur place ce qui n'est plus vrai. Cette relecture humaine est le seul verdict
sur la justesse de la documentation ; c'est exactement la part que `doc_impact`
ne peut pas faire à votre place.
