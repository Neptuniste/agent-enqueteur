# agent-enqueteur

Mini-projet 2 NLP : agent conversationnel spécialisé (Transformer instructionnel + LoRA + Gradio).

Livrables : `agent.ipynb` (exécuté), `rapport.pdf` (4 pages max), `data/`, adaptateur LoRA (lien HF), `README.txt`.

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
| `src/` | code partagé : `config.py` (modèle, hyperparamètres, chemins), puis `game_state.py`, `prompt_builder.py`, `llm.py`, `app.py` |
| `cases/main_case/` | affaire jouable = affaire de test (`case.json`, `characters/`, `assets/`) |
| `cases/training/` | affaires d'entraînement et de validation |
| `data/` | `build_dataset.py` + splits train / val / test (découpés **par affaire**) |
| `eval/` | grille d'évaluation, script d'évaluation |
| `results/` | courbes de loss, tableaux d'évaluation |
| `adapter/` | adaptateur LoRA local, **non versionné** |
| `rapport/` | sources du rapport |
| `docs/` | cahier des charges |

Les poids (adaptateur LoRA, checkpoints) ne vont **pas** dans git : `model.push_to_hub(...)` puis lien dans `README.txt` et `src/config.py`.

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

Étapes du cahier des charges (§14), à attribuer :

| Étape | Contenu | Membre |
|---|---|---|
| 1 | Cadrage, fiche JSON, scénario de l'affaire jouable, 5 interrogatoires | |
| 2 | Observation du modèle, choix entre 2 candidats | |
| 3 | Baseline, comparaison de 2 prompts | |
| 4 | Scénarios, génération, critique et relecture des données | |
| 5 | Entraînement QLoRA, courbes, choix de l'arrêt | |
| 6 | Évaluation baseline vs LoRA, analyse d'erreurs | |
| 7 | Moteur de jeu et interface Gradio | |
| 8 | Rapport de 4 pages, README | |
