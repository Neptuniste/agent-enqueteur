"""Paramètres partagés (voir docs/cahier_des_charges.md, §8, §9.5 et §10)."""

SEED = 42

# Candidat par défaut, comparé à Qwen/Qwen2.5-3B-Instruct en partie 2
MODEL_NAME = "Qwen/Qwen3-4B-Instruct-2507"

# Historique : nombre d'échanges (joueur + personnage) conservés
MAX_HISTORY_TURNS = 6
MAX_LENGTH = 2048    # entraînement : un exemple (système + 1 à 4 tours)
MAX_CONTEXT = 3072   # inférence : système + historique + réponse (§8.4)

GENERATION_KWARGS = dict(
    max_new_tokens=150,
    do_sample=True,
    temperature=0.7,
    top_p=0.9,
    repetition_penalty=1.1,
)

# Découpage par personnage (§9.5)
VAL_CHARACTERS = ["celeste_moreau"]   # un témoin
TEST_CHARACTERS = ["armand_riviere"]  # une fausse piste, jamais vue à l'entraînement

# Chemins relatifs à la racine du repo
CASES_DIR = "cases"
DATA_DIR = "data"
ADAPTER_DIR = "adapter"
RESULTS_DIR = "results"

ADAPTER_REPO = ""  # lien Hugging Face Hub de l'adaptateur LoRA
