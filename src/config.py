"""Paramètres partagés (voir docs/cahier_des_charges.md, §8 et §10)."""

SEED = 42

# Candidat par défaut, confirmé ou remplacé en partie 2
MODEL_NAME = "Qwen/Qwen2.5-3B-Instruct"

# Historique : nombre d'échanges (joueur + personnage) conservés
MAX_HISTORY_TURNS = 6
MAX_LENGTH = 2048

GENERATION_KWARGS = dict(
    max_new_tokens=150,
    do_sample=True,
    temperature=0.7,
    top_p=0.9,
    repetition_penalty=1.1,
)

# Chemins relatifs à la racine du repo
CASES_DIR = "cases"
DATA_DIR = "data"
ADAPTER_DIR = "adapter"
RESULTS_DIR = "results"

ADAPTER_REPO = ""  # lien Hugging Face Hub de l'adaptateur LoRA
