# agent-enqueteur

Mini-projet 2 NLP : un agent conversationnel qui joue les suspects d'une enquête policière (*Le Dernier Verre du Faisan Doré*, Paris, 1928). Il repose sur un Transformer instructionnel (Qwen3-4B), une adaptation QLoRA et une interface Gradio.

**Rendu : 23 octobre 2026.** Livrables :
- `agent.ipynb`, exécuté ;
- `rapport.pdf`, 4 pages au plus ;
- `data/` ;
- l'adaptateur LoRA (lien Hugging Face) ;
- `README.txt`.

Référence : [docs/cahier_des_charges.md](docs/cahier_des_charges.md). Le planning jusqu'au rendu est au §14.

## Jouer

Le jeu a deux enquêtes :
- **Le Dernier Verre du Faisan Doré** (1928), celle des données d'entraînement ;
- **Dernière au Théâtre du Miroir** (1929), une intrigue que le modèle n'a jamais vue, qui teste sa généralisation.

Il existe aussi une interface ludique (`src/jeu/`), plus complète que celle du rendu (`src/app.py`). Elle offre :
- un choix des enquêtes ;
- la une du journal ;
- des portraits ;
- des répliques tapées à la machine ;
- des pièces à glisser sur le suspect ;
- un carnet des aveux ;
- une accusation avec score et grade.

| Comment | Commande |
|---|---|
| Sans modèle ni GPU (mode démo : les personnages répondent avec leur fiche) | double-clic sur `jouer_demo.bat`, ou `python jouer.py --demo` |
| Avec le modèle et l'adaptateur, sur Colab | ouvrir `jouer.ipynb` et exécuter ses trois cellules |
| Avec le modèle, sur une machine avec GPU | `python jouer.py` (`--sans-adaptateur` pour la baseline, `--share` pour un lien public) |
| L'interface du rendu, sur une autre affaire | `python jouer.py --classique --affaire theatre_miroir` |

Le mode démo sert à essayer l'interface et à tester une affaire : il ne contient aucun modèle de langage, et ne peut rien divulguer, puisqu'il ne lit que le prompt.

## État du projet (21 octobre 2026)

Tout est fait sauf le rendu lui-même :

- **Données** : 540 dialogues relus par l'équipe (539 acceptés, 1 rejeté) ; `data/train.jsonl` (467) et `data/val.jsonl` (72).
- **Entraînement** sur Colab : meilleur pas 60, perte de validation 1,045 ; adaptateur publié sur https://huggingface.co/Neptuniste/faisan-dore-lora.
- **Évaluation** : métriques automatiques et notation des 68 réponses, faite par Claude faute de notateurs (`results/notes_claude.csv`, `results/tableau_evaluation.md`).
- **Notebook** `agent.ipynb` exécuté (37 cellules, sans erreur), commentaires complétés.
- **Rapport** : `rapport.pdf` (4 pages et une annexe), source dans `rapport/rapport.md`.

Il reste :

1. Remplacer « [troisième membre] » dans `README.txt` et `rapport/rapport.md`, puis régénérer `rapport.pdf`.
2. Relire le notebook et le rapport, rédigés avec l'aide de Claude.
3. Déposer le rendu : `agent.ipynb`, `rapport.pdf`, `README.txt`, le lien du dépôt (données) et celui de l'adaptateur.
4. Avant de rendre le dépôt public, **demander l'autorisation à Team Break** : l'affaire est adaptée de leur scénario.

Facultatif : évaluer la seconde affaire sur GPU (14 requêtes de `data/test_theatre.jsonl`), avec les commandes de l'étape 3.8 de [GUIDE.md](GUIDE.md).

## Mise en route (une fois par membre)

```powershell
git clone https://github.com/Neptuniste/agent-enqueteur.git
cd agent-enqueteur
python -m venv .venv
.venv\Scripts\activate
pip install torch                       # CPU suffit pour relire les données et lancer les contrôles
pip install -r requirements.txt
pip install nbstripout jupyter
nbstripout --install                    # retire les sorties des brouillons au commit
Add-Content .git\info\attributes "agent.ipynb -filter"   # sauf le notebook final, rendu exécuté
```

> Ne pas cloner dans OneDrive : la synchronisation entre en conflit avec git.

Sans GPU, `ESSAI_RAPIDE = True` dans `agent.ipynb` fait tourner tout le notebook avec Qwen2.5-0.5B en une vingtaine de minutes. Cela suffit pour vérifier qu'une modification ne casse rien.

## Organisation

| Dossier | Contenu |
|---|---|
| `agent.ipynb` | notebook final (installation, puis parties 1 à 7 du sujet), qui garde ses sorties |
| `src/` | `config.py` (modèle, hyperparamètres), `game_state.py` (état de la partie), `prompt_builder.py` (message système), `guard.py` (filtre de sortie), `llm.py` (chargement, génération), `train.py` (QLoRA), `app.py` (Gradio) |
| `cases/main_case/` | l'affaire : `case.json`, `characters/` (8 fiches), `assets/` (rapports, plan, 12 pièces) |
| `cases/theatre_miroir/` | la seconde affaire, au même format (7 fiches, 11 pièces), jamais vue à l'entraînement |
| `src/jeu/` | interface ludique : `moteur.py` (parties, score), `catalogue.py` (affaires, portraits), `demo.py` (mode sans modèle), `interface.py` et `web/` (page de jeu) |
| `jouer.py`, `jouer.ipynb`, `jouer_demo.bat` | lanceurs du jeu (ligne de commande, Colab, double-clic) |
| `cases/check_case.py` | vérificateur de l'affaire, **à relancer après chaque modification d'une fiche** |
| `data/` | `raw/` (plan, répliques rédigées, exemples à relire), `generate.py`, `relire.py`, `build_dataset.py`, `train.jsonl` / `val.jsonl` (découpés par personnage), `test.jsonl` (écrit à la main), `interrogatoires_types.json` (mise au point) |
| `eval/` | `grille_evaluation.md` (grille et 34 requêtes), `evaluate.py` (génération, métriques, notation à l'aveugle) |
| `results/` | courbes de perte, réponses évaluées, feuilles de notation, tableaux |
| `adapter/` | adaptateur LoRA local, **non versionné** (publié sur le Hugging Face Hub) |
| `rapport/` | brouillon du rapport |
| `notebooks/` | brouillons par partie, facultatifs (le notebook final est `agent.ipynb`) |
| `docs/` | cahier des charges, sujet |

## Contrôles à relancer

```powershell
python cases/check_case.py              # l'affaire : 0 erreur attendu avant de commiter
python cases/check_case.py --autotest   # le vérificateur détecte-t-il des erreurs plantées ?
python eval/evaluate.py verifier        # le jeu de test respecte le §11
python data/build_dataset.py --stats    # données : découpage, longueurs, aucune question de test reprise
python tests/test_interface.py          # jeu et interface Gradio, avec un générateur factice (sans modèle)
python tests/test_jeu.py                # interface ludique : moteur, puis parcours dans le navigateur (pip install playwright)
python cases/check_case.py cases/theatre_miroir --autotest   # la seconde affaire
```

## Modifier l'affaire

Toute modification de `cases/main_case/` (fiche, pièce, chronologie) doit repasser `check_case.py`. Il vérifie :
- le format (§7 du cahier des charges) ;
- que la chaîne d'indices reste jouable jusqu'à la solution ;
- qu'aucune vérité verrouillée ni aucun mot interdit n'apparaît dans les 208 prompts rendus ;
- les longueurs en tokens ;
- la cohérence des heures avec la chronologie.

Il ne juge pas le récit : relire aussi les prompts (`src/prompt_builder.py`).

Après une modification de fiche, les dialogues déjà rédigés pour ce personnage sont signalés comme périmés par `build_dataset.py` : il faut relancer `python data/generate.py assembler <personnage>`, puis les relire.

## Workflow git

```powershell
git pull
git checkout -b nom-de-la-tache
# ... travail ...
git add .
git commit -m "message clair"
git push -u origin nom-de-la-tache
```

Ouvrir ensuite une Pull Request vers `main`, relue par un autre membre.
