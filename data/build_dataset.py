"""Construit data/train.jsonl, data/val.jsonl et data/test.jsonl.

Format d'une ligne (format chat de transformers) :
{"messages": [{"role": "system", "content": "..."},
              {"role": "user", "content": "..."},
              {"role": "assistant", "content": "..."}]}
"""

import json
import random
from pathlib import Path

DATA_DIR = Path(__file__).parent
SEED = 42
SPLITS = {"train": 0.8, "val": 0.1, "test": 0.1}


def load_dialogues():
    """À compléter : renvoie la liste des dialogues (200 à 1 000 exemples courts)."""
    return []


def main():
    dialogues = load_dialogues()
    random.Random(SEED).shuffle(dialogues)
    n = len(dialogues)
    n_train = int(n * SPLITS["train"])
    n_val = int(n * SPLITS["val"])
    parts = {
        "train": dialogues[:n_train],
        "val": dialogues[n_train:n_train + n_val],
        "test": dialogues[n_train + n_val:],
    }
    for name, rows in parts.items():
        with open(DATA_DIR / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"{name}: {len(rows)} exemples")


if __name__ == "__main__":
    main()
