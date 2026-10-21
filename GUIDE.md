# Guide pas à pas : de la relecture au rendu

Chaque étape dit quoi faire, où cliquer, et quoi taper. Les commandes se tapent dans PowerShell, ouvert dans le dossier du projet (`C:\dev\agent-enqueteur`).

**Ordre : 0 → 1 → 2 → 3 → 4 → 5 → 6.** Ne lancez pas Colab (étape 3) avant d'avoir fini les étapes 1 et 2.

---

## Étape 0 : préparer (une seule fois, 15 min)

**0.1 Récupérer la dernière version du projet**, sur la branche `affaire-faisan-dore` : tout le travail y est, `main` ne contient que le squelette du début.

```
git fetch
git checkout affaire-faisan-dore
git pull
```

Si vous n'avez pas encore le projet, tapez d'abord `git clone https://github.com/Neptuniste/agent-enqueteur.git`, puis `cd agent-enqueteur`, puis les trois commandes ci-dessus. Le dépôt est privé : il faut avoir été ajouté comme collaborateur sur GitHub.

**0.2 Créer un jeton GitHub.** Colab en a besoin pour télécharger le dépôt, qui est privé. C'est le propriétaire du dépôt qui le crée.

1. Sur github.com, cliquez sur votre photo en haut à droite, puis sur **Settings**.
2. Tout en bas du menu de gauche : **Developer settings**, puis **Personal access tokens**, puis **Fine-grained tokens**, puis **Generate new token**.
3. Remplissez :
   - *Token name* : `colab` ;
   - *Expiration* : 30 jours ;
   - *Repository access* : **Only select repositories**, puis choisissez `agent-enqueteur` ;
   - *Permissions*, puis *Repository permissions*, puis *Contents* : **Read-only**.
4. Cliquez sur **Generate token**.
5. Copiez le jeton (il commence par `github_pat_`) et gardez-le dans un endroit sûr.

**0.3 Créer un jeton Hugging Face.** Il sert à publier l'adaptateur.

1. Sur huggingface.co, créez un compte si besoin.
2. Cliquez sur votre photo en haut à droite, puis sur **Settings**, puis sur **Access Tokens**, puis sur **Create new token**.
3. Choisissez le *Token type* **Write**, donnez le nom `colab`, puis cliquez sur **Create token**.
4. Copiez le jeton : il commence par `hf_`.
5. Notez votre pseudo Hugging Face. C'est la fin de l'adresse de votre profil : `huggingface.co/votre-pseudo`.

---

## Étape 1 : relire les 540 dialogues (lundi 19, à se répartir)

Les dialogues ont été réécrits le 19 octobre pour être plus clairs. Faites d'abord `git pull` (étape 0.1) : une relecture commencée avant cette date est à refaire.

Les 7 personnages sont répartis entre trois relecteurs. Chacun ne relit que les siens : chaque personnage a son propre fichier, donc vos envois ne se gênent pas.

| Relecteur | Personnages | Dialogues |
|---|---|---|
| 1 (Thibaut, déjà commencé) | `celeste_moreau`, `lucien_fabre` | 72 + 78 = 150 |
| 2 | `leon_perrin`, `josephine_laurent` | 78 + 78 = 156 |
| 3 | `rose_delorme`, `marguerite_delorme`, `henri_berthier` | 78 × 3 = 234, mais les répliques les plus courtes |

Comptez environ 1 h par personnage. Pour relire, il suffit d'avoir Python 3.10 ou plus récent : rien à installer.

**1.1 Pour chacun de vos personnages, lancez la relecture.** Exemple pour Rose :

```
python data\relire.py rose_delorme
```

**1.2 Pour chaque dialogue affiché, tapez une lettre puis Entrée :**

| Touche | Quand |
|---|---|
| `o` | le dialogue est bon : conforme à la fiche, ton juste, rien d'inventé, 2 à 5 phrases |
| `r` | à jeter ; tapez ensuite un motif en une ligne |
| `c` | une réplique est à corriger ; tapez le numéro du tour, puis la nouvelle réplique en entier |
| `f` | afficher la fiche du personnage, en cas de doute |
| `q` | s'arrêter ; tout est enregistré, et la relance reprend où vous en étiez |

**1.3 Une fois vos personnages finis, envoyez votre travail :**

```
git add data
git commit -m "Relecture : rose_delorme"
git pull
git push
```

**1.4 Pour voir l'avancement de toute l'équipe :**

```
python data\relire.py --bilan
```

**1.5 Quand le bilan n'affiche plus aucun « a_relire », une seule personne lance :**

```
git pull
.venv\Scripts\python.exe data\build_dataset.py
git add data
git commit -m "Données relues : train et val"
git push
```

Le script doit afficher `train: … exemples` et `val: … exemples`. S'il dit « Aucun exemple accepté », la relecture n'est pas finie.

*(Si vous n'avez pas de dossier `.venv`, remplacez `.venv\Scripts\python.exe` par `python`.)*

---

## Étape 2 : indiquer où publier l'adaptateur (déjà faite)

`src\config.py`, ligne 50, contient déjà :

```python
ADAPTER_REPO = "Neptuniste/faisan-dore-lora"
```

Le notebook créera ce dépôt sur Hugging Face et y publiera l'adaptateur, grâce au jeton `HF_TOKEN`, qui doit appartenir au compte Neptuniste.

---

## Étape 3 : tout lancer sur Colab (mardi 20, 1 h 30 à 2 h)

**3.1 Ouvrez le notebook.** Ouvrez cette adresse dans Chrome, en étant connecté à votre compte Google :

https://colab.research.google.com/github/Neptuniste/agent-enqueteur/blob/affaire-faisan-dore/agent.ipynb

Si Colab demande l'accès à GitHub, acceptez.

**3.2 Choisissez un GPU.** Menu **Exécution**, puis **Modifier le type d'exécution**, puis **GPU T4**, puis **Enregistrer**.

**3.3 Ajoutez les deux jetons.** Dans la barre de gauche, cliquez sur l'icône **clé** (*Secrets*), puis sur **Ajouter un secret**, deux fois :

| Nom | Valeur | Accès au notebook |
|---|---|---|
| `GITHUB_TOKEN` | le jeton `github_pat_…` | coché |
| `HF_TOKEN` | le jeton `hf_…` | coché |

**3.4 Laissez la première cellule de code telle quelle :** `ESSAI_RAPIDE = False`, `ENTRAINER = True`.

**3.5 Lancez.** Menu **Exécution**, puis **Tout exécuter**.
- Si Colab dit « Ce notebook n'a pas été créé par Google » : **Exécuter quand même**.
- S'il demande l'accès aux secrets : **Autoriser**.

**3.6 Laissez l'onglet ouvert jusqu'à la fin.** Repères :
- sous la 2ᵉ cellule de code s'affiche `Projet : /content/agent-enqueteur` ;
- la **section 5** (entraînement) est la plus longue : 45 à 60 min ;
- la **section 6** (évaluation) prend environ 25 min. Le navigateur télécharge ensuite `resultats.zip` ; si Chrome demande d'autoriser plusieurs téléchargements, acceptez ;
- en **section 7**, un lien `https://….gradio.live` apparaît : c'est le jeu, vous pouvez déjà y jouer.

**3.7 En cas d'erreur.** Si une cellule s'arrête sur une erreur en rouge, copiez le message et envoyez-le.

Si la première cellule affiche « Secret … illisible », le secret manque, porte un autre nom, ou n'a pas l'accès au notebook. Corrigez-le dans l'icône **clé**, ou collez le jeton dans le champ masqué qui apparaît. Ne collez jamais un jeton dans une cellule de code : il serait enregistré dans le notebook.

Si le message contient `CUDA out of memory`, le GPU manque de mémoire :
1. Dans `src\config.py`, mettez `per_device_train_batch_size=1` et `gradient_accumulation_steps=8`.
2. Poussez la modification.
3. Dans Colab : **Exécution**, puis **Redémarrer la session et tout exécuter**.

**3.8 Facultatif, 10 min, dans la même session.** Ce test mesure le jeu sur la seconde affaire, que le modèle n'a jamais vue.

Tout en bas du notebook, cliquez sur **+ Code**, puis collez et exécutez la cellule suivante :

```python
!python eval/evaluate.py --affaire cases/theatre_miroir --test data/test_theatre.jsonl --resultats results/theatre generer --version baseline
!python eval/evaluate.py --affaire cases/theatre_miroir --test data/test_theatre.jsonl --resultats results/theatre generer --version lora --adaptateur Neptuniste/faisan-dore-lora
!python eval/evaluate.py --test data/test_theatre.jsonl --resultats results/theatre auto
import shutil
from google.colab import files
files.download(shutil.make_archive("theatre", "zip", root_dir=".", base_dir="results/theatre"))
```

Gardez le tableau affiché : il va dans le rapport, section 5.

**3.9 Récupérez les résultats sur votre PC.**
1. Décompressez `resultats.zip`, et `theatre.zip` si vous avez fait 3.8, **dans le dossier du projet**. Vous devez obtenir par exemple `C:\dev\agent-enqueteur\results\eval_lora.jsonl`.
2. Puis :
   ```
   git add results
   git commit -m "Résultats de l'entraînement et de l'évaluation"
   git push
   ```

---

## Étape 4 : noter à l'aveugle (mercredi 21, 2 personnes, environ 2 h chacune)

> **21 octobre : faute de notateurs disponibles, la notation a été faite par Claude** (`results\notes_claude.csv`, un commentaire par note). Le tableau et le graphique sont prêts (`results\tableau_evaluation.md`, `results\scores_evaluation.png`), et le rapport le signale. Les étapes ci-dessous ne servent plus qu'à ajouter un notateur humain : copiez d'abord `results\notation_aveugle.csv` en `results\notes_A.csv`. L'agrégation calcule alors l'accord avec Claude.

**4.1 Les deux feuilles sont prêtes** : `results\notes_A.csv` pour le premier notateur, `results\notes_B.csv` pour le second (deux copies de `results\notation_aveugle.csv`). Faites `git pull`, puis chacun ne modifie que sa propre feuille.

**4.2 Lancez la notation au clavier**, sans Excel. Chacun ne note que sa propre feuille (`A` ou `B`) :

```
python eval\noter.py A
```

La grille complète est dans `eval\grille_evaluation.md`. N'ouvrez **pas** `notation_cles.json` : il dit quelle réponse vient de quelle version.

**4.3 Pour chaque réponse affichée, tapez une seule ligne puis Entrée** :
- un chiffre (0, 1 ou 2) par critère affiché, dans l'ordre, par exemple `2122` ;
- éventuellement suivi d'un commentaire : `2122 invente un chiffre`.

Les critères sans objet (« - ») ne sont pas demandés. `g` réaffiche la grille, `s` passe la réponse, `q` quitte. Tout est enregistré après chaque réponse, et la relance reprend où vous en étiez. `python eval\noter.py A --bilan` donne l'avancement.

**4.4 Envoyez votre feuille** quand elle est finie : `git add results`, `git commit -m "Notes A"`, `git pull`, `git push`.

*(La feuille reste un CSV ordinaire : on peut aussi la remplir dans Excel, en mettant 0, 1 ou 2 dans les colonnes de notes, en laissant les « - », puis en l'enregistrant au format CSV.)*

**4.5 Mesurez votre accord**, avant toute discussion :

```
.venv\Scripts\python.exe eval\evaluate.py agreger results\notes_A.csv results\notes_B.csv
```

Notez la ligne « Accord entre notateurs : … % » : ce chiffre va dans le rapport.

**4.6 Discutez vos désaccords.** Mettez-vous d'accord sur les cases où vos notes diffèrent, et corrigez les deux fichiers.

**4.7 Recalculez et envoyez :**

```
.venv\Scripts\python.exe eval\evaluate.py agreger results\notes_A.csv results\notes_B.csv
git add results
git commit -m "Notation à l'aveugle"
git push
```

Le tableau final est dans `results\tableau_evaluation.md`, et le graphique dans `results\scores_evaluation.png`.

---

## Étape 5 : exécution finale et finitions (jeudi 22 et vendredi 23)

**5.1 Rouvrez le notebook dans Colab** avec la même adresse qu'en 3.1. Choisissez le GPU T4 ; les secrets sont toujours là.

**5.2 Dans la première cellule de code, mettez `ENTRAINER = False`.** L'adaptateur est déjà publié, et les réponses déjà notées seront réutilisées.

**5.3 Lancez.** Menu **Exécution**, puis **Tout exécuter** (environ 45 min).

**5.4 Complétez les commentaires.**
1. Ouvrez **Modifier**, puis **Rechercher et remplacer** (Ctrl+H), et cherchez `À VÉRIFIER`, puis `À COMPLÉTER` : il y a 7 endroits.
2. Pour chacun, double-cliquez sur la cellule de texte et lisez la consigne entre `<!--` et `-->`.
3. Corrigez le texte pour qu'il corresponde aux sorties affichées, puis supprimez la ligne `<!-- … -->`.
4. En section 6.3, écrivez l'analyse de 5 cas. `comparer("T04")` affiche les deux réponses d'une requête.

**5.5 Récupérez le notebook exécuté.**
1. Menu **Fichier**, puis **Télécharger**, puis **Télécharger le fichier .ipynb**.
2. Remplacez `C:\dev\agent-enqueteur\agent.ipynb` par le fichier téléchargé.
3. Puis :
   ```
   git add agent.ipynb
   git commit -m "Notebook exécuté"
   git push
   ```

**5.6 Écrivez le rapport.**
1. Dans `rapport\rapport.md`, remplacez tous les `[…]` et `[À COMPLÉTER]` par vos chiffres. Ils sont dans :
   - `results\tableau_evaluation.md` ;
   - `results\courbes_loss.png` ;
   - `results\scores_evaluation.png`.
2. Mettez-le en page dans Word ou Google Docs : 4 pages au maximum.
3. Exportez-le en PDF sous le nom `rapport.pdf`, à la racine du projet.

**5.7 Complétez `README.txt` :**
- remplacez « Membres : (à compléter) » par vos noms ;
- le lien de l'adaptateur est déjà renseigné : `https://huggingface.co/Neptuniste/faisan-dore-lora`.

**5.8 Envoyez le tout :**

```
git add rapport.pdf README.txt
git commit -m "Rendu"
git push
```

---

## Étape 6 : rendre (vendredi 23)

Déposez, selon les consignes du cours :
- `agent.ipynb`, exécuté ;
- `rapport.pdf` ;
- `README.txt` ;
- les données : le dossier `data\`, ou le lien du dépôt GitHub ;
- le lien de l'adaptateur : `https://huggingface.co/Neptuniste/faisan-dore-lora`.

Avant de rendre le dépôt GitHub public, demandez l'autorisation à Team Break : l'affaire principale est adaptée de leur scénario.

---

## Pour jouer, à tout moment

- **Sur votre PC, sans GPU :** double-cliquez sur `jouer_demo.bat`.
- **Avec le vrai modèle**, une fois l'adaptateur publié :
  1. Ouvrez `jouer.ipynb` dans Colab, comme en 3.1, en remplaçant `agent.ipynb` par `jouer.ipynb` dans l'adresse.
  2. Choisissez le GPU T4, puis **Tout exécuter**.
  3. Cliquez sur le lien `gradio.live`.
