# agent-enqueteur

Mini-projet 2 NLP : un agent conversationnel qui joue les suspects d'une enquête policière (*Le Dernier Verre du Faisan Doré*, Paris, 1928). Il repose sur un Transformer instructionnel (Qwen3-4B), une adaptation QLoRA et une interface Gradio.

**Rendu : 23 octobre 2026.** Livrables :
- `agent.ipynb`, exécuté ;
- `rapport.pdf`, 4 pages au plus ;
- `data/` ;
- l'adaptateur LoRA (lien Hugging Face) ;
- `README.txt`.

Référence : [docs/cahier_des_charges.md](docs/cahier_des_charges.md). Le planning jusqu'au rendu est au §14.

## Ce qu'il reste à faire

Le code est écrit et testé sur CPU avec un petit modèle. Les 540 dialogues sont rédigés et passent les contrôles automatiques. Il reste les étapes qui demandent un GPU ou des humains :

1. **Relire les données** : 540 exemples, à répartir par personnage.
   - Lancer `python data/relire.py <personnage>` ; `python data/relire.py --bilan` donne l'avancement.
   - Ensuite, `python data/build_dataset.py` écrit `data/train.jsonl` et `data/val.jsonl`, à commiter.
2. **Exécuter `agent.ipynb` sur Colab avec un GPU T4.**
   - Pour l'ouvrir : *Fichier > Ouvrir un notebook > GitHub*, en cochant « Inclure les dépôts privés ».
   - La première cellule de code clone le dépôt. Si le dépôt est privé, elle a besoin d'un jeton `GITHUB_TOKEN` dans les secrets Colab (icône de clé), avec l'accès du notebook activé.
   - Avant l'entraînement, renseigner `ADAPTER_REPO` dans `src/config.py` (par exemple `Neptuniste/faisan-dore-lora`) et se connecter à Hugging Face : `from huggingface_hub import login; login()`.
   - Après l'entraînement et la génération des réponses de la section 6, **commiter `results/`** : courbes, bilan, `eval_*.jsonl` et feuille de notation. Une nouvelle session Colab repart d'un clone du dépôt, et ces fichiers doivent y être.
     - Sur Colab, la cellule qui suit la création de la feuille télécharge `resultats.zip`.
     - Le décompresser à la racine du dépôt, puis commiter.
     - Si `ADAPTER_REPO` est vide, elle télécharge aussi `adaptateur.zip`, à garder hors de git.
3. **Noter à l'aveugle** :
   - copier `results/notation_aveugle.csv` en `results/notes_A.csv` et `results/notes_B.csv` ;
   - chaque notateur remplit sa copie avec la grille (`eval/grille_evaluation.md`) ;
   - commiter les copies, puis relancer la cellule d'agrégation du notebook.
   - Tant que la feuille existe, le notebook ne régénère pas les réponses : les notes restent valables.
4. **Compléter le notebook** :
   - chercher `À VÉRIFIER` et `À COMPLÉTER` (commentaires invisibles une fois le notebook rendu) ;
   - adapter les commentaires aux sorties réelles ;
   - écrire l'analyse des cinq cas de la section 6.3.
5. **Rapport** : partir de [rapport/rapport.md](rapport/rapport.md), le compléter avec les chiffres obtenus, puis l'exporter en PDF.
6. **Rendu** :
   - exécuter tout le notebook une dernière fois avec `ENTRAINER = False` : l'adaptateur évalué est alors celui du Hub ;
   - le télécharger depuis Colab (Fichier > Télécharger > .ipynb) et le commiter avec ses sorties ;
   - compléter `README.txt` (membres, lien de l'adaptateur).
7. Avant de rendre le dépôt public, **demander l'autorisation à Team Break** : l'affaire est adaptée de leur scénario.

## Mise en route (une fois par membre)

```powershell
git clone https://github.com/Neptuniste/agent-enqueteur.git
cd agent-enqueteur
python -m venv .venv
.venv\Scripts\activate
pip install torch                       # CPU suffit pour relire les données et lancer les contrôles
pip install -r requirements.txt
pip install nbstripout jupyter
nbstripout --install                    # retire les sorties des brouillons au commit (agent.ipynb les garde)
```

> Ne pas cloner dans OneDrive : la synchronisation entre en conflit avec git.

Sans GPU, `ESSAI_RAPIDE = True` dans `agent.ipynb` fait tourner tout le notebook avec Qwen2.5-0.5B en une vingtaine de minutes. Cela suffit pour vérifier qu'une modification ne casse rien.

## Organisation

| Dossier | Contenu |
|---|---|
| `agent.ipynb` | notebook final (installation, puis parties 1 à 7 du sujet), qui garde ses sorties |
| `src/` | `config.py` (modèle, hyperparamètres), `game_state.py` (état de la partie), `prompt_builder.py` (message système), `guard.py` (filtre de sortie), `llm.py` (chargement, génération), `train.py` (QLoRA), `app.py` (Gradio) |
| `cases/main_case/` | l'affaire : `case.json`, `characters/` (8 fiches), `assets/` (rapports, plan, 12 pièces) |
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
