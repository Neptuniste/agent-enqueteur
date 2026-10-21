# Évaluation : baseline vs lora

## Notation par Claude selon la grille, un seul notateur (notes moyennes, de 0 à 2)

| Critère | baseline | lora |
|---|---|---|
| pertinence | 1.26 | 1.68 |
| role_format | 1.24 | 1.91 |
| historique | 1.29 | 1.29 |
| hors_perimetre | 1.40 | 1.70 |
| invention | 0.91 | 1.65 |
| bonus_mensonge | 1.92 | 1.67 |
| bonus_mise_en_scene | 0.94 | 1.03 |
| **moyenne des 5 critères principaux** | 1.22 | 1.64 |

### Par groupe de personnages (moyenne des 5 critères principaux)

| Groupe | baseline | lora |
|---|---|---|
| personnages vus | 1.17 | 1.61 |
| personnage jamais vu | 1.26 | 1.67 |
| personnage de validation | 1.33 | 2.00 |

### Plus grands écarts (lora − baseline, moyenne des critères principaux)

- T26 : +1.67
- T25 : +1.50
- T28 : +1.33
- T15 : +1.33
- T08 : +1.33
- T29 : -1.00
- T18 : -0.67
- T11 : -0.50
- T12 : -0.33

## Métriques automatiques (tous les tirages, sans filtre de sortie)

| Métrique | baseline | lora |
|---|---|---|
| réponses analysées | 180 | 180 |
| taux de fuite | 1% | 0% |
| taux d'aveu correct (confrontations) | 100% | 80% |
| sortie du rôle | 0% | 0% |
| moins de 2 phrases | 0% | 0% |
| plus de 5 phrases | 21% | 1% |
| plus d'une didascalie | 0% | 0% |
| longueur moyenne (tokens) | 88 | 46 |

### Taux de fuite par groupe de personnages

| Groupe | baseline | lora |
|---|---|---|
| personnages vus | 1% | 0% |
| personnage jamais vu | 0% | 0% |
| personnage de validation | 0% | 0% |

### Mots interdits échappés (les plus fréquents)

- baseline : « pharmacien » ×1
- lora : aucun
