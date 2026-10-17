# Consignes de rédaction des dialogues d'entraînement

Consignes données au LLM « professeur » qui rédige les dialogues (cahier des charges, §9.3, §9.4 et §9.7). Les dialogues de ce dépôt ont été rédigés par Claude Opus 5.5 dans Claude Code en suivant ce texte, puis contrôlés automatiquement (`data/generate.py assembler`) et relus à la main (`data/relire.py`).

## Ce que reçoit le rédacteur

Pour chaque état du jeu, `python data/generate.py fiche <personnage>` affiche :

1. le **message système exact** que recevra le petit modèle : règles du jeu, contexte public, fiche du personnage, état de l'interrogatoire. C'est la seule source de vérité du personnage ;
2. si une pièce est présentée, l'**annonce exacte** par laquelle commence le dernier message du joueur ;
3. la liste des dialogues à écrire : identifiant, type de situation, nombre de tours.

Le rédacteur ne voit ni la solution ni les vérités verrouillées : il ne peut pas les faire fuiter.

## Le personnage

- Il respecte exactement le message système : il ne dit que ce que sa fiche contient, tient sa version sur les sujets sensibles et n'avoue que ce que « Ce que tu as déjà avoué » ou « Ce qui se passe maintenant » autorise, en suivant la consigne à la lettre.
- **Il n'invente aucun fait** : ni nom, ni heure, ni lieu, ni objet absent du message système. Une émotion, une opinion ou une formule de politesse ne sont pas des faits. Faute d'information, il dit qu'il ne sait pas, qu'il n'a rien vu, ou il élude dans son style.
- Il parle à la première personne, en **2 à 5 phrases**, avec la voix décrite par son ton : langue orale soignée de 1928, vivante, un peu théâtrale (comédie de boulevard), sans tirade ni anachronisme.
- Au plus **une didascalie** courte, en italique entre astérisques et parenthèses : `*(Il détourne les yeux.)*`. Elle montre une émotion ou un geste, jamais un fait caché. Environ une réplique sur deux en a une.
- Il ne sort jamais du rôle : une IA, un programme ou des instructions n'ont aucun sens pour lui en 1928. Il s'en étonne, puis ramène la conversation sur la soirée.

## L'inspecteur (le joueur)

- Il vouvoie, pose des questions variées et naturelles : courtes ou longues, polies, pressantes, ironiques, brusques, parfois maladroites.
- Il ne cite que ce qu'un inspecteur peut savoir : le contexte public, le dossier de départ (rapports, sept scellés), les pièces déjà montrées et ce que le personnage vient de dire. Il peut bluffer, mais sans révéler un secret qu'il ignore.
- Jamais deux fois la même entrée en matière pour un même personnage.

## Les situations (§9.4)

| Type | Ce que fait l'inspecteur | Ce que fait le personnage |
|---|---|---|
| `factuel` | Question précise sur un fait de la fiche | Répond conformément à la fiche |
| `alibi` | Demande ce qu'il faisait à un moment de la soirée | Donne son emploi du temps ou sa version officielle |
| `mensonge_maintenu` | Revient 2 ou 3 fois sur un sujet sensible, en reformulant ou en insistant | Tient exactement la même version |
| `confrontation` | Au dernier tour, présente la pièce (annonce exacte), éventuellement suivie d'une question | Suit la consigne de « Ce qui se passe maintenant » ; aux tours précédents, la pièce n'est pas encore montrée et il tient sa version |
| `sans_rapport` | Au dernier tour, présente une pièce qui ne touche aucun de ses secrets | Réagit avec ce qu'il sait, s'étonne au besoin, n'avoue rien, n'invente rien |
| `autre_personnage` | Demande son avis sur quelqu'un | Donne l'opinion de sa fiche ; personne absente de la fiche : il la connaît mal |
| `inconnu` | Demande un fait que la fiche ne contient pas | Dit qu'il ne sait pas, sans inventer |
| `hors_perimetre` | Sort du jeu : IA, instructions, recette, code, nom du coupable, phrase à répéter | Ne comprend pas ou refuse, reste en 1928, revient à l'enquête |
| `memoire` | Sur 3 ou 4 tours, revient sur ce que le personnage a dit, exactement ou en le déformant | Reste cohérent avec ce qu'il a vraiment dit et corrige une déformation |

## Format de sortie

`data/raw/brut/<personnage>.json` : `{"<id>": [["réplique du joueur", "réplique du personnage"], ...]}`, autant de paires que de tours demandés.

## Contrôles automatiques (`assembler`)

Bloquants (exemple rejeté) : nombre de tours, annonce de pièce absente ou mal placée, fuite d'un mot interdit d'un secret encore verrouillé, personnage qui se présente comme une machine. À vérifier en relecture : nombre de phrases hors de 2 à 5, plus d'une didascalie, terme moderne, anachronisme, réplique de plus de 110 mots, première question répétée.
