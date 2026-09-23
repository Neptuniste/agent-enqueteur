"""Paramètres partagés par tous les notebooks (à compléter après la partie 1)."""

MODEL_NAME = ""  # ex. "Qwen/Qwen2.5-0.5B-Instruct" — à choisir ensemble

SYSTEM_PROMPT = """"""  # rôle, périmètre et refus de l'agent

MAX_HISTORY_TURNS = 4  # nombre d'échanges conservés dans l'historique

GENERATION_KWARGS = dict(
    max_new_tokens=256,
    do_sample=True,
    temperature=0.7,
    top_p=0.9,
)

ADAPTER_REPO = ""  # lien Hugging Face Hub de l'adaptateur LoRA
