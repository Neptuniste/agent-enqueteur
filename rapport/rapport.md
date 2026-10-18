<!--
Brouillon du rapport (4 pages maximum hors annexes). Les passages [À COMPLÉTER] attendent les résultats
de l'exécution sur Colab (agent.ipynb) et la notation. Export : pandoc rapport.md -o ../rapport.pdf
(ou copier dans un traitement de texte). Garder les figures results/courbes_loss.png et
results/scores_evaluation.png.
-->

# Le Dernier Verre du Faisan Doré : un agent conversationnel qui joue les suspects d'une enquête

Mini-projet 2 de NLP. Équipe : [À COMPLÉTER]. 23 octobre 2026.

## 1. Cas d'usage et périmètre

**Le jeu.** L'agent sert un jeu d'enquête en français. Paris, nuit du 13 au 14 octobre 1928 : Victor Delorme, patron d'un bar clandestin, est empoisonné dans son bureau fermé à clé.

- Le joueur, dans le rôle de l'inspecteur, interroge les huit personnes présentes.
- Il peut leur présenter douze pièces à conviction, dont cinq n'apparaissent qu'après certains aveux.
- Il désigne enfin le coupable.

L'affaire est librement adaptée d'un scénario de murder party de Team Break, avec une chronologie, des pièces et des fiches réécrites.

**Le rôle de l'agent.** Il joue *un* personnage à la fois. Il doit :

- répondre en français, à la première personne, en 2 à 5 phrases, avec au plus une didascalie ;
- ne donner que les faits de sa fiche ;
- tenir sa version officielle, qui peut être un mensonge ;
- n'avouer un secret que devant la bonne pièce ;
- se souvenir de l'historique.

**Les refus.** Il refuse, sans sortir de son rôle, les demandes hors de l'univers du jeu, les tentatives de briser le quatrième mur et la question « qui est le coupable ? ». Ce périmètre est étroit, donc évaluable.

**Architecture.** Le principe est : *les faits dans le prompt, le comportement dans la LoRA*. Le code garde la vérité : pièces possédées, pièces montrées, aveux obtenus. Il construit à chaque tour le message système du personnage, et cinq barrières empêchent la solution de fuir :

1. **Cloisonnement** : une seule fiche par prompt.
2. **Secrets verrouillés** : la vérité n'est injectée qu'à l'aveu, avec une consigne qui en fixe les limites.
3. **Meurtre absent du prompt** : il n'y figure jamais, même pour la coupable.
4. **Filtre de sortie** : il régénère une réponse qui contient un mot interdit d'un secret encore verrouillé.
5. **Comportement appris** : c'est le rôle de l'adaptateur.

Un seul modèle et un seul adaptateur jouent les huit personnages.

## 2. Modèle, observation et baseline

**Choix du modèle.** Nous avons comparé Qwen3-4B-Instruct-2507 et Qwen2.5-3B-Instruct sur les premières questions de cinq interrogatoires types. Ces interrogatoires forment un jeu de mise au point, distinct du test. Nous avons retenu **Qwen3-4B-Instruct-2507**, pour trois raisons : [À COMPLÉTER : français, tenue du rôle, exemple], la licence Apache 2.0 et le budget mémoire. Quantifié en 4 bits, il tient sur un T4.

**Observation (partie 2 du notebook).**

- *Tokenisation.* Le tokenizer est un BPE au niveau des octets, avec 151 936 tokens. Le français coûte [À COMPLÉTER] tokens par mot.
- *Logits.* Le modèle renvoie des logits de forme `(1, n, 151 936)`. La dernière ligne seulement sert à générer.
- *Unembedding.* Le dernier état caché, projeté par la matrice de sortie (partagée avec les embeddings), redonne exactement ces logits. La « lentille des logits » montre que la prédiction n'émerge que dans les dernières couches [À COMPLÉTER].
- *Attention causale.* Ajouter des tokens ne change pas les logits des positions précédentes.
- *Décodage.* La température module l'entropie de la distribution [chiffres]. Top-k et top-p coupent la queue d'où viennent les dérives.

Nous en tirons les réglages suivants : température 0,7, top-p 0,9, top-k 20, pénalité de répétition 1,1, 150 tokens au plus.

**Baseline.** C'est le modèle sans adaptateur, avec :

- un message système construit par le code : règles, contexte public, fiche, état de la partie ;
- le chat template du tokenizer ;
- un historique limité à 6 échanges et à 3 072 tokens. Les aveux restent dans le message système, donc la cohérence survit à la troncature.

Nous avons comparé deux formulations sur 14 questions de pression, avec 3 tirages chacune :

- **prompt A**, fiche complète avec l'ordre de ne rien révéler : [X] % de réponses avec fuite ;
- **prompt B**, fiche verrouillée : [Y] %.

Nous retenons B : le modèle ne peut pas révéler ce qu'il ignore. Reste ce que le prompt ne règle pas : la baseline [À COMPLÉTER : sort du rôle, avoue trop ou pas assez, invente des détails…].

## 3. Données

**Constitution.** Aucun corpus ne montre un suspect qui ment, puis avoue exactement ce que dit sa fiche. Nous avons donc constitué 540 dialogues de 1 à 4 tours, en quatre étapes.

1. **Plan.** Un plan fixe pour chaque exemple :
   - le personnage ;
   - le type de situation : factuel, alibi, mensonge maintenu, confrontation, pièce sans rapport, autre personnage, information inconnue, hors périmètre, mémoire ;
   - l'état du jeu (tout verrouillé, pièce présentée, après un aveu, dans des proportions d'environ 60/25/15) ;
   - le nombre de tours.
2. **Rédaction.** Les répliques ont été rédigées avec Claude (Opus 5.5) dans Claude Code, en suivant des consignes de style théâtral.
3. **Contrôles automatiques.** Ils vérifient les tours, l'annonce des pièces, les fuites de mots interdits, la sortie du rôle, la longueur, les didascalies et les anachronismes.
4. **Relecture humaine.** Chaque exemple a été relu : [Z] % ont été rejetés et [W] corrigés.

**Format.** Le message système de chaque exemple est reconstruit par le code, à l'identique de celui du jeu : le modèle apprend un comportement, pas des faits. La perte ne porte que sur les répliques du personnage. Quand une pièce est présentée au dernier tour, seule la réplique d'aveu compte.

**Diversité.** Les chiffres ci-dessous datent d'avant la relecture et sont à mettre à jour :

- 27 % des 937 répliques portent une didascalie, avec 149 didascalies distinctes. Les plus fréquentes sont des traits prévus dans les fiches (Rose se raidit, Perrin toussote).
- On compte 893 questions distinctes sur 937.
- Les répliques presque identiques d'un exemple à l'autre reprennent la version officielle d'un personnage : c'est la cohérence recherchée.

**Découpage par personnage.** Avec une seule affaire, on ne découpe pas ligne par ligne :

- l'entraînement porte sur 6 personnages ([N] exemples) ;
- la validation porte sur Céleste Moreau ([M] exemples, jamais vue à l'entraînement) ;
- le test (§5) couvre tous les personnages, dont Armand Rivière, que le modèle n'a jamais vu.

Aucune question de test ne figure dans les données : c'est vérifié automatiquement, à l'identique et par similarité. Tous les personnages sont fictifs et les dialogues ne contiennent aucune donnée personnelle, ce que confirme une recherche automatique de motifs.

## 4. Adaptation QLoRA

| Réglage | Valeur |
|---|---|
| Modèle de base | Qwen3-4B-Instruct-2507, gelé, NF4 4 bits (double quantification, calcul en float16) |
| LoRA | r = 16, α = 32, dropout 0,05 ; couches q, k, v, o, gate, up, down ([P] M de paramètres entraînés, soit [Q] %) |
| Optimisation | taux 2e-4, cosinus, échauffement 5 %, lots de 2 × 4 (accumulation), paged AdamW 8 bits |
| Durée | 4 époques au plus ; perte de validation tous les 10 pas ; arrêt anticipé après 3 évaluations sans progrès |
| Longueur maximale | 2 048 tokens (le plus long exemple en compte 1 454) |

[Figure : results/courbes_loss.png]

**Arrêt de l'entraînement.** [À COMPLÉTER]

- La perte de validation atteint son minimum au pas [s] (époque [e]), à [v].
- L'entraînement s'arrête au pas [t] : [arrêt anticipé, ou fin des époques].
- Le meilleur adaptateur, selon la validation, est rechargé puis publié : [lien Hugging Face].

L'écart entre les pertes d'entraînement et de validation après le minimum signale le début du par cœur.

## 5. Évaluation avant et après adaptation

**Protocole.** La grille et les requêtes ont été figées avant le premier entraînement. Le jeu de test compte 34 requêtes écrites à la main :

- 30 requêtes à un tour, avec au moins 2 par type de situation ;
- 4 scénarios de 5 à 10 tours ;
- 13 requêtes sur Armand Rivière.

La baseline est le même modèle, adaptateur désactivé, avec le même prompt B, les mêmes réglages et la même graine par requête. Le filtre de sortie est coupé pour évaluer le modèle seul. Deux notateurs ont noté à l'aveugle, ordre mélangé et version masquée, avec une échelle de 0 à 2 et cinq critères plus deux bonus. Taux d'accord entre notateurs : [A] %.

| Critère (moyenne sur 2) | Baseline | LoRA |
|---|---|---|
| Pertinence et correction | | |
| Rôle et format | | |
| Historique | | |
| Hors périmètre | | |
| Informations inventées | | |
| Bonus : mensonge tenu / mise en scène | | |
| Moyenne, personnages vus / Armand (jamais vu) | | |
| Taux de fuite (sans filtre) / aveu correct | | |

[À COMPLÉTER : analyse d'au moins cinq réussites ou erreurs, avec citations courtes. Pistes :
- confrontation sur Armand (T04) : l'aveu reste-t-il limité à la consigne ?
- accusation directe de la coupable (T12) ;
- hors périmètre (T10, T25, T30) ;
- mémoire (T11) ;
- scénario long de Rose (S02) ;
- erreurs restantes ou introduites par la LoRA.]

**Généralisation à une intrigue inédite** (facultatif). Une seconde affaire originale, « Dernière au Théâtre du Miroir » (1929), n'a servi ni à l'entraînement ni à la validation. Elle compte 7 personnages et 11 pièces.

Sur ses 14 requêtes de test, et avec les métriques automatiques seulement :
- taux de fuite : [baseline] % contre [LoRA] % ;
- aveux corrects en confrontation : [baseline] % contre [LoRA] %.

[À COMPLÉTER : une phrase sur ce que cela dit de la généralisation, au-delà d'une nouvelle fiche (Armand) : une nouvelle intrigue.]

## 6. Interface

L'interface Gradio est lancée depuis le notebook et comprend :

- un encadré de présentation : rôle, règles et limites de l'agent ;
- un onglet Dossier : rapports, plan et pièces débloquées ;
- un onglet Interrogatoire, avec :
  - le choix du personnage ;
  - la zone de conversation et le champ de saisie ;
  - la présentation d'une pièce ;
  - l'annonce des nouvelles pièces ;
  - le bouton Réinitialiser, qui efface l'historique du personnage sans annuler ses aveux ;
- un onglet Accusation : verdict, aveu final et solution.

Chaque réponse passe par le filtre de sortie. Si la génération échoue, l'état de la partie est rétabli.

## 7. Limites et améliorations

**Limites.**

- **Une seule affaire.** Armand Rivière mesure la généralisation à une nouvelle fiche, pas à une nouvelle intrigue.
- **Données rédigées par un modèle.** Elles sont relues, mais leur style est plus homogène que celui de vrais joueurs.
- **Filtre lexical.** Il ne détecte pas une paraphrase du secret. La protection principale reste le verrouillage des fiches.
- **Évaluation humaine.** Elle repose sur deux notateurs et 34 requêtes.
- **Latence.** Il faut compter quelques secondes par réponse sur un T4.

**Pistes.**

- Écrire une seconde affaire pour tester la généralisation.
- Collecter des parties jouées, puis affiner les aveux par préférence (DPO).
- Remplacer le filtre lexical par un détecteur sémantique ou un juge automatique.
- Afficher la réponse au fil de la génération (streaming).

## Usage de l'IA

Claude (Opus 5.5, Anthropic), utilisé dans Claude Code, a servi à deux choses :

- rédiger les dialogues d'entraînement, d'après le plan et les fiches ;
- écrire le code : préparation des données, entraînement, évaluation, interface et notebook.

L'équipe a fait les choix de conception, consignés dans le cahier des charges. Elle a écrit le jeu de test et a relu les données ainsi que le code [À COMPLÉTER : préciser qui a fait quoi].
