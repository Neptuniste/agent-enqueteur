# Grille d'évaluation (à figer AVANT le premier entraînement)

Référence : cahier des charges §11. Échelle : 0 = non satisfait, 1 = partiel, 2 = satisfait.

| Critère | Déclinaison pour notre agent | 0 | 1 | 2 |
|---|---|---|---|---|
| Pertinence et correction | Réponse cohérente avec la fiche | Ne répond pas | Partiellement | Clairement |
| Respect du rôle et du format | Personnage, français, 2 à 5 phrases, 1 didascalie au plus | Sort du personnage | Ton incohérent ou trop long | Respectés |
| Prise en compte de l'historique | Pas de contradiction avec les tours précédents | Se contredit | Ignore l'historique | Cohérent |
| Détection du hors périmètre | Ne brise pas le 4ᵉ mur, ne révèle pas la solution | Sort du jeu ou révèle | Reste flou | Reste dans le rôle et recadre |
| Absence d'informations inventées | Aucun fait absent de la fiche ; secret révélé seulement si la condition est remplie | Invente ou révèle trop tôt | Détail invérifiable anodin | Aucune invention |
| Bonus : mensonge tenu | Le personnage ne lâche pas sa version sans preuve | Avoue sans preuve | Hésite, laisse filtrer | Tient sa version |
| Bonus : mise en scène | Voix du personnage, didascalie juste | Plat ou anachronique | Correct sans plus | Vivant, voix reconnaissable |

## Protocole

- Même configuration de prompt (retenue en partie 3) et mêmes paramètres pour la baseline et la LoRA ; graine fixée par requête.
- 1 tirage noté à la main ; 5 tirages pour les métriques automatiques (fuite, aveu correct, longueur).
- Requêtes à un tour et « mémoire » : historique écrit à l'avance, identique pour les deux versions.
- Scénarios multi-tours : questions du joueur écrites à l'avance, chaque version garde son propre historique, notation sur l'ensemble.
- Notation à l'aveugle (ordre mélangé, version masquée), 2 notateurs si possible.

## Requêtes de test (≥ 24, jamais vues à l'entraînement)

Écrites dans `data/test.jsonl`. Au moins 2 par type, 4 scénarios multi-tours (dont 2 de 10 tours), au moins un tiers sur Armand Rivière, le personnage tenu à l'écart de l'entraînement et de la validation.

| # | Personnage | Vu à l'entraînement ? | Type (§9.4) | Requête | Comportement attendu |
|---|---|---|---|---|---|
| 1 | | | | | |
