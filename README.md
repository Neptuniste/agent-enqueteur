# agent-enqueteur

Mini-projet 2 NLP : agent conversationnel spécialisé (Transformer instructionnel + LoRA + Gradio).

**Rendu : 23 octobre 2026.** Livrables : `agent.ipynb` (exécuté), `rapport.pdf` (4 pages max), `data/`, adaptateur LoRA (lien HF), `README.txt`.

## Mise en route (une fois par membre)

```powershell
git clone https://github.com/Neptuniste/agent-enqueteur.git
cd agent-enqueteur
pip install -r requirements.txt
nbstripout --install   # retire les sorties des notebooks au commit
```

> Ne pas cloner dans OneDrive (conflits de synchro avec git).

## Organisation

Référence : [docs/cahier_des_charges.md](docs/cahier_des_charges.md) (§13 pour l'arborescence).

| Dossier | Contenu |
|---|---|
| `agent.ipynb` | notebook final, assemblé à la fin (garde ses sorties) |
| `notebooks/` | brouillons, **un notebook par partie** pour éviter les conflits |
| `src/` | code partagé : `config.py` (modèle, hyperparamètres, chemins), puis `game_state.py`, `prompt_builder.py`, `guard.py`, `llm.py`, `app.py` |
| `cases/main_case/` | l'affaire unique, *Le Dernier Verre du Faisan Doré* (`case.json`, `characters/`, `assets/`) |
| `cases/check_case.py` | vérificateur de l'affaire, **à relancer après chaque modification d'une fiche** |
| `data/` | `raw/` (dialogues relus), `build_dataset.py`, splits train / val (découpés **par personnage**), `test.jsonl` écrit à la main |
| `eval/` | grille d'évaluation, script d'évaluation |
| `results/` | courbes de loss, tableaux d'évaluation |
| `adapter/` | adaptateur LoRA local, **non versionné** |
| `rapport/` | sources du rapport |
| `docs/` | cahier des charges, sujet |

Les poids (adaptateur LoRA, checkpoints) ne vont **pas** dans git : `model.push_to_hub(...)` puis lien dans `README.txt` et `src/config.py`.

## Modifier l'affaire

Toute modification de `cases/main_case/` (fiche, pièce, chronologie) doit repasser le vérificateur :

```powershell
python cases/check_case.py              # 0 erreur attendu avant de commiter
python cases/check_case.py --autotest   # vérifie aussi que le vérificateur détecte des erreurs plantées
```

Il contrôle le format (§7 du cahier des charges), que la chaîne d'indices est jouable jusqu'à la solution, qu'aucune vérité verrouillée ni aucun mot interdit n'apparaît dans les 208 prompts rendus, les longueurs en tokens et la cohérence des heures avec la chronologie. Il ne juge pas le récit : relire aussi les prompts (`src/prompt_builder.py`).

## Workflow

```powershell
git pull
git checkout -b nom-de-la-tache
# ... travail ...
git add .
git commit -m "message clair"
git push -u origin nom-de-la-tache
```
Puis Pull Request sur GitHub vers `main`, relue par un autre membre.

## Répartition

Étapes du cahier des charges (§14, planning daté par semaine), à attribuer :

| Étape | Contenu | Membre |
|---|---|---|
| 1 | Cadrage, affaire, fiches, 5 interrogatoires | |
| 2 | Observation du modèle, choix entre 2 candidats | |
| 3 | Baseline, comparaison de 2 prompts | |
| 4 | Génération, critique et relecture des données | |
| 5 | Entraînement QLoRA, courbes, choix de l'arrêt | |
| 6 | Évaluation baseline vs LoRA, analyse d'erreurs | |
| 7 | Moteur de jeu et interface Gradio | |
| 8 | Rapport de 4 pages, README | |
