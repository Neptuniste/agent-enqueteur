# Le Dernier Verre du Faisan Doré

**Un jeu d'enquête où une intelligence artificielle joue les suspects.**

Paris, nuit du 13 au 14 octobre 1928. Au Faisan Doré, un bar clandestin de Montmartre, le patron Victor Delorme est retrouvé mort dans son bureau fermé à clé, empoisonné au cyanure. Personne n'a quitté les lieux.

Vous êtes l'inspecteur. Vous interrogez les huit personnes présentes, vous leur montrez des pièces à conviction, et vous désignez le coupable. Chaque personnage est joué par un modèle de langage : il répond librement à vos questions, tient sa version, ment pour protéger ses secrets, et finit par avouer quand vous lui montrez la bonne preuve.

Projet réalisé pour le mini-projet 2 du cours de traitement automatique du langage (NLP) : partir d'un modèle de langage existant, l'observer, l'adapter à un rôle précis, mesurer le résultat et l'intégrer dans une interface.

[![Jouer sur Google Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Neptuniste/agent-enqueteur/blob/main/jouer.ipynb)

---

## Jouer

Le jeu propose deux enquêtes :
- **Le Dernier Verre du Faisan Doré** (1928), l'affaire principale, sur laquelle l'IA a été entraînée ;
- **Dernière au Théâtre du Miroir** (1929), une seconde affaire que l'IA n'a jamais vue pendant son entraînement.

Choisissez l'une des trois façons de lancer le jeu.

### 1. Avec la vraie IA, gratuitement sur Google Colab (recommandé)

Il faut seulement un compte Google.

1. Cliquez sur le bouton **Open in Colab** ci-dessus : le notebook `jouer.ipynb` s'ouvre.
2. Choisissez une carte graphique : menu **Exécution > Modifier le type d'exécution > GPU T4**, puis **Enregistrer**.
3. Lancez tout : menu **Exécution > Tout exécuter**.
4. Si une case demande un jeton GitHub, laissez-la vide et appuyez sur **Entrée** : le dépôt est public.
5. Attendez quelques minutes (le modèle se télécharge au premier lancement), puis cliquez sur le lien `https://….gradio.live` qui s'affiche en bas : le jeu s'ouvre dans un nouvel onglet.

Sans carte graphique, le notebook lance automatiquement le mode démo décrit ci-dessous.

### 2. En mode démo, sur votre ordinateur, sans IA

Pour découvrir le jeu sans carte graphique ni compte. Dans ce mode, les personnages répondent avec des phrases tirées de leur fiche, sans modèle de langage : les réponses sont plus raides, mais tout le jeu fonctionne (dossier, pièces, aveux, accusation).

1. Téléchargez le projet : sur GitHub, bouton vert **Code > Download ZIP**, puis décompressez le dossier.
2. Installez Python 3.10 à 3.13 depuis [python.org](https://www.python.org/downloads/) si vous ne l'avez pas (sous Windows, cochez « Add python.exe to PATH »).
3. Lancez le jeu :
   - **sous Windows** : double-cliquez sur `jouer_demo.bat`. La première fois, il installe ce qu'il faut (une à deux minutes) ;
   - **sous macOS ou Linux** : dans un terminal ouvert dans le dossier,
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     pip install gradio==6.30.0
     python jouer.py --demo
     ```

Le jeu s'ouvre dans votre navigateur.

### 3. Avec la vraie IA, sur un ordinateur équipé d'une carte graphique NVIDIA

Il faut environ 6 Go de mémoire graphique.

```bash
pip install torch            # version CUDA : voir https://pytorch.org
pip install -r requirements.txt
python jouer.py              # ajouter --share pour obtenir un lien public temporaire
```

---

## Comment se déroule une partie

1. **Choisissez une enquête**, puis lisez la une du journal et le dossier : rapport de police, rapport du médecin légiste, plan des lieux et premières pièces à conviction.
2. **Interrogez les suspects.** Posez vos questions comme vous le feriez à l'oral, ou utilisez les questions suggérées. Attention : les personnages peuvent mentir.
3. **Montrez des pièces.** Glissez une pièce dans la salle d'interrogatoire, ou cliquez sur « Montrer ». Devant la bonne pièce, un personnage avoue. Certains aveux font apparaître de nouvelles pièces, et le jeu indique comment vous les avez obtenues (une fouille, une déposition…).
4. **Tenez votre carnet.** Il garde la trace des aveux obtenus, et vous pouvez y prendre des notes.
5. **Accusez.** Désignez le coupable et appuyez votre accusation sur les pièces qui prouvent le mobile, le moyen et l'occasion. Vous obtenez un verdict, un score sur 100 et un grade, de *Inspecteur stagiaire* à *Commissaire divisionnaire*. En cas d'erreur, vous pouvez demander la solution.

Le score récompense l'enquête plus que le flair : trouver le coupable rapporte 40 points, chaque preuve juste 8, les preuves décisives que vous avez débloquées jusqu'à 26, et les aveux obtenus jusqu'à 10.

---

## Comment ça marche

- **Le modèle.** Les répliques sont écrites par Qwen3-4B-Instruct, un modèle de langage libre d'environ 4 milliards de paramètres, qui tient sur une seule carte graphique.
- **L'adaptation.** Le modèle a été spécialisé pour ce rôle par une adaptation légère, appelée LoRA. Le modèle d'origine reste intact : on lui ajoute un petit module de 33 millions de paramètres (0,8 % du modèle), entraîné sur 467 dialogues d'interrogatoire et validé sur 72 autres, tous relus un par un par l'équipe. Le module appris est publié sur [Hugging Face](https://huggingface.co/Neptuniste/faisan-dore-lora).
- **Le code garde la vérité.** C'est le programme, et non l'IA, qui sait qui a fait quoi. À chaque question, il donne au modèle la seule fiche du personnage interrogé. Un secret n'y entre qu'au moment où vous montrez la bonne pièce, et la solution du meurtre n'y figure jamais. L'IA ne peut donc pas révéler ce qu'elle ne sait pas.
- **Un filtre de sécurité.** Chaque réponse est relue avant d'être affichée. Si elle contient un mot lié à un secret encore caché, elle est réécrite.

---

## Résultats

Le modèle de base et le modèle adapté ont répondu aux mêmes 34 questions de test, jamais vues pendant l'entraînement.

| Critère | Modèle de base | Modèle adapté |
|---|---|---|
| Respect du rôle et du format (note sur 2) | 1,24 | **1,91** |
| Absence d'informations inventées (note sur 2) | 0,91 | **1,65** |
| Refus des demandes hors du jeu (note sur 2) | 1,40 | **1,70** |
| Réponses trop longues (plus de 5 phrases) | 21 % | **1 %** |
| Secrets révélés trop tôt | 1 % | **0 %** |

Les notes de 0 à 2 suivent une grille fixée avant l'entraînement ; elles ont été attribuées par un seul notateur, Claude (Anthropic). Les pourcentages sont mesurés automatiquement.

L'adaptation rend les personnages bien plus fidèles à leur rôle, mais tout n'est pas parfait : dans les longues conversations, un personnage peut se contredire, et il arrive encore qu'il invente un détail. Le [rapport](rapport.pdf) détaille ces erreurs, avec des exemples.

---

## Contenu du dépôt

| Élément | Ce que c'est |
|---|---|
| `jouer.ipynb`, `jouer_demo.bat`, `jouer.py` | les trois façons de lancer le jeu (Colab, double-clic, ligne de commande) |
| `agent.ipynb` | le notebook du projet, déjà exécuté : observation du modèle, données, entraînement, évaluation, interface |
| `rapport.pdf` | le rapport du projet (sources dans `rapport/`) |
| `README.txt` | les instructions d'exécution détaillées du notebook |
| `cases/` | les deux enquêtes : fiches des personnages, pièces à conviction, rapports, plans |
| `data/` | les dialogues d'entraînement et de validation, le jeu de test, et les scripts qui les produisent |
| `src/` | le code du jeu et du modèle ; `src/jeu/` contient l'interface de jeu |
| `eval/` | la grille d'évaluation et le script d'évaluation |
| `results/` | les courbes d'entraînement, les réponses évaluées et les tableaux de résultats |
| `tests/` | les tests automatiques du jeu et de l'interface |
| `docs/` | le sujet du projet et le cahier des charges |

### Refaire les expériences

[![Ouvrir agent.ipynb dans Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Neptuniste/agent-enqueteur/blob/main/agent.ipynb)

Ouvrez `agent.ipynb` dans Colab avec un GPU T4, puis **Exécution > Tout exécuter**. Par défaut, le notebook réutilise l'adaptateur déjà entraîné. Pour tout réentraîner, mettez `ENTRAINER = True` dans la première cellule de code (comptez 1 h 30 à 2 h en tout). Le détail est dans [README.txt](README.txt).

<details>
<summary><b>Pour les développeurs : vérifications</b></summary>

```bash
python cases/check_case.py                    # cohérence de l'affaire principale (0 erreur attendu)
python cases/check_case.py cases/theatre_miroir
python eval/evaluate.py verifier              # le jeu de test
python data/build_dataset.py --stats          # les données : découpage, longueurs, aucune question de test reprise
python tests/test_interface.py                # interface du notebook, sans modèle
python tests/test_jeu.py                      # interface de jeu (avec Playwright : parcours complet dans le navigateur)
```

Toute modification d'une fiche ou d'une pièce doit repasser `cases/check_case.py`. Il vérifie que l'enquête reste jouable jusqu'à la solution et qu'aucun secret ne peut apparaître trop tôt dans les messages envoyés au modèle.

</details>

---

## Crédits

- **Équipe** : Thibaut Laheurte, Nathan Signoud, Capucine Lardiere (2026).
- **Scénario d'origine** : « Le Dernier Verre du Faisan Doré », murder party gratuite de [Team Break](https://team-break.fr/scenario-murder-party-gratuit), librement adaptée pour ce projet.
- **Modèle** : [Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) (licence Apache 2.0) ; adaptateur publié sur [Hugging Face](https://huggingface.co/Neptuniste/faisan-dore-lora).

