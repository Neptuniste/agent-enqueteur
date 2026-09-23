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

| Dossier | Contenu |
|---|---|
| `agent.ipynb` | notebook final, assemblé à la fin (garde ses sorties) |
| `notebooks/` | brouillons, **un notebook par partie** pour éviter les conflits |
| `src/config.py` | modèle, prompt système, paramètres de génération communs |
| `data/` | `build_dataset.py` + splits train / val / test |
| `eval/` | grille d'évaluation et requêtes de test |
| `rapport/` | sources du rapport |

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

| Membre | Parties |
|---|---|
| | 1 Définition de l'agent + 2 Observation du modèle |
| | 3 Baseline / prompting + 7 Interface Gradio |
| | 4 Données + grille d'évaluation |
| | 5 LoRA + 6 Évaluation |
