LE DERNIER VERRE DU FAISAN DORÉ
Un agent conversationnel qui joue les suspects d'une enquête policière
Mini-projet 2 NLP : du Transformer pré-entraîné à une application de dialogue

Membres : (à compléter)
Rendu : 23 octobre 2026


CONTENU

  agent.ipynb          notebook exécuté, de l'installation à l'interface (sections 0 à 7)
  rapport.pdf          rapport (4 pages hors annexes)
  data/                données : train.jsonl, val.jsonl, test.jsonl, et les scripts qui les produisent
  adaptateur LoRA      https://huggingface.co/Neptuniste/faisan-dore-lora (ou dossier adapter/)
  src/                 code du jeu et du modèle, importé par le notebook
  eval/                grille et script d'évaluation
  cases/main_case/     l'affaire : fiches des personnages, pièces à conviction, plan
  docs/                cahier des charges et sujet


1. EXÉCUTION SUR GOOGLE COLAB (recommandée)

  a. Ouvrir agent.ipynb dans Colab.
     Choisir un GPU : Exécution > Modifier le type d'exécution > GPU T4.
  b. Si le dépôt GitHub est privé, enregistrer un jeton GitHub dans les secrets Colab,
     sous le nom GITHUB_TOKEN.
  c. Exécution > Tout exécuter.
     La première cellule de code clone le dépôt et installe requirements.txt.
     Durée totale : 1 h 30 à 2 h, dont 45 à 60 min d'entraînement.
  d. Pour réutiliser l'adaptateur publié au lieu d'entraîner :
     mettre ENTRAINER = False dans la cellule de réglages.
     L'adaptateur est alors téléchargé depuis le dépôt Hugging Face indiqué
     dans src/config.py (ADAPTER_REPO).
  e. La dernière cellule lance l'interface Gradio et affiche un lien public temporaire.


2. EXÉCUTION LOCALE

  Python 3.10 à 3.12, GPU NVIDIA conseillé : environ 6 Go pour jouer, un T4 (15 Go) pour entraîner.

    python -m venv .venv
    .venv\Scripts\activate             (Windows ; sous Linux ou macOS : source .venv/bin/activate)
    pip install torch                   (version CUDA : voir https://pytorch.org)
    pip install -r requirements.txt jupyter
    jupyter notebook agent.ipynb

  Sans GPU, mettre ESSAI_RAPIDE = True : tout le notebook tourne avec un petit modèle
  (Qwen2.5-0.5B-Instruct) et des calculs réduits. Cela vérifie l'installation ;
  les résultats ne sont pas significatifs.


3. DONNÉES

  data/train.jsonl et data/val.jsonl sont fournis.
  Pour les reconstruire à partir des dialogues relus de data/raw/ :
    python data/build_dataset.py

  Jeu de test : data/test.jsonl (34 requêtes écrites à la main). Pour le contrôler :
    python eval/evaluate.py verifier

  Fabrication des données : docs/cahier_des_charges.md, section 9.


4. ÉVALUATION EN LIGNE DE COMMANDE (facultatif : mêmes fonctions que le notebook)

    python eval/evaluate.py generer --version baseline
    python eval/evaluate.py generer --version lora --adaptateur adapter
    python eval/evaluate.py feuille
    python eval/evaluate.py agreger results/notes_A.csv results/notes_B.csv


5. INTERFACE SEULE

  Dans Python, avec un GPU :
    from src.llm import charger_modele
    from src.app import lancer
    model, tokenizer = charger_modele(adaptateur="adapter")
    lancer(model, tokenizer)


6. LE JEU COMPLET (facultatif)

  Une interface plus ludique, avec deux enquêtes : la seconde, « Dernière au Théâtre du Miroir »,
  n'a jamais été vue à l'entraînement.
    jouer.ipynb                     sur Colab, avec le modèle et l'adaptateur
    python jouer.py                 avec un GPU
    python jouer.py --demo          sans modèle ni GPU : les personnages répondent avec leur fiche
                                    (sous Windows : double-clic sur jouer_demo.bat)


Matériel : Google Colab, GPU NVIDIA T4 (15 Go).
Modèle de base : Qwen/Qwen3-4B-Instruct-2507 (licence Apache 2.0).
Affaire librement adaptée de « Le Dernier Verre du Faisan Doré » (Team Break, https://team-break.fr).
Seconde affaire, « Dernière au Théâtre du Miroir » : originale, écrite pour le projet avec l'aide de Claude.
Dialogues d'entraînement rédigés avec l'aide de Claude (Anthropic), puis relus par l'équipe.
