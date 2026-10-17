"""Construit data/train.jsonl et data/val.jsonl (cahier des charges, §9.5 et §9.6).

Entrée : data/raw/<personnage>.jsonl, dialogues générés puis relus à la main.
Une ligne :
{"personnage": "marc_dubois", "situation": "alibi", "statut": "ok",
 "messages": [{"role": "system", "content": "..."},
              {"role": "user", "content": "..."},
              {"role": "assistant", "content": "..."}]}

Le découpage se fait par personnage, jamais par ligne : les personnages de
VAL_CHARACTERS vont en validation, ceux de TEST_CHARACTERS sont exclus
(réservés au test), tous les autres vont en entraînement.
data/test.jsonl est écrit à la main et n'est pas produit par ce script.
"""

import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import SEED, TEST_CHARACTERS, VAL_CHARACTERS  # noqa: E402

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"


def load_dialogues():
    """Lit tous les dialogues relus de data/raw/."""
    rows = []
    for path in sorted(RAW_DIR.glob("*.jsonl")):
        with open(path, encoding="utf-8") as f:
            rows.extend(json.loads(line) for line in f if line.strip())
    return rows


def main():
    dialogues = load_dialogues()
    status = Counter(d.get("statut") for d in dialogues)
    kept = [d for d in dialogues if d.get("statut") == "ok"]
    if dialogues:
        rejected = len(dialogues) - len(kept)
        print(f"relus : {len(dialogues)}, rejetés : {rejected} "
              f"({rejected / len(dialogues):.0%}), statuts : {dict(status)}")

    parts = {"train": [], "val": []}
    for d in kept:
        if d["personnage"] in TEST_CHARACTERS:
            continue
        split = "val" if d["personnage"] in VAL_CHARACTERS else "train"
        parts[split].append({"messages": d["messages"]})

    for name, rows in parts.items():
        random.Random(SEED).shuffle(rows)
        with open(DATA_DIR / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"{name}: {len(rows)} exemples")


if __name__ == "__main__":
    main()
