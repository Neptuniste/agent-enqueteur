"""Construit data/train.jsonl et data/val.jsonl (cahier des charges, §9.5 et §9.6).

Entrée : data/raw/<personnage>.jsonl, produits par `data/generate.py assembler` puis relus
avec `data/relire.py`. Seuls les exemples au statut « ok » sont gardés.

Contrôles faits avant d'écrire quoi que ce soit :
- découpage par personnage : VAL_CHARACTERS en validation, TEST_CHARACTERS exclus, le reste en entraînement ;
- le message système est reconstruit depuis l'état avec prompt_builder (fiches et règles actuelles),
  et un écart avec la version relue est signalé (fiche modifiée depuis la rédaction) ;
- aucune question du jeu de test (data/test.jsonl) ne doit se retrouver dans les données ;
- les exemples de plus de MAX_LENGTH tokens sont écartés et comptés (tokenizer du modèle si disponible).

    python data/build_dataset.py            # écrit train.jsonl et val.jsonl
    python data/build_dataset.py --stats    # statistiques sur tous les exemples, relus ou non, sans rien écrire
"""

import argparse
import difflib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import MAX_LENGTH, MODEL_NAME, SEED, TEST_CHARACTERS, VAL_CHARACTERS  # noqa: E402
from src.game_state import charger_affaire  # noqa: E402
from src.guard import normaliser  # noqa: E402
from src.prompt_builder import build_system_prompt  # noqa: E402

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
TEST = DATA_DIR / "test.jsonl"
ANNONCE = re.compile(r"^\*\(L'inspecteur vous montre [^)]*\)\*\s*")
SEUIL_SIMILARITE = 0.85  # au-delà, une question d'entraînement est jugée trop proche d'une question de test


def charger_dialogues():
    """Tous les exemples assemblés de data/raw/*.jsonl."""
    rows = []
    for path in sorted(RAW_DIR.glob("*.jsonl")):
        with open(path, encoding="utf-8") as f:
            rows.extend(json.loads(line) for line in f if line.strip())
    return rows


def compteur_tokens():
    """Longueur d'un exemple une fois le chat template appliqué, ou None si transformers est absent."""
    try:
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained(MODEL_NAME)
    except Exception:
        return None

    def compter(messages):
        ids = tok.apply_chat_template(messages, tokenize=True)
        if hasattr(ids, "keys"):  # certaines versions renvoient un dictionnaire
            ids = ids["input_ids"]
        return len(ids)
    return compter


def questions_du_test():
    """Questions du joueur dans le jeu de test, sans l'annonce de pièce."""
    questions = []
    for ligne in TEST.read_text(encoding="utf-8").splitlines():
        if not ligne.strip():
            continue
        item = json.loads(ligne)
        if item["type"] == "scenario":
            questions += [t["question"] for t in item["tours"]]
        else:
            questions.append(item["question"])
            questions += [m["content"] for m in item.get("historique", []) if m["role"] == "user"]
    return {normaliser(ANNONCE.sub("", q)) for q in questions if len(ANNONCE.sub("", q)) > 15}


def verifier_fuite_test(exemples, test):
    """Questions d'entraînement identiques ou trop proches d'une question de test."""
    alertes = []
    for e in exemples:
        for m in e["messages"]:
            if m["role"] != "user":
                continue
            q = normaliser(ANNONCE.sub("", m["content"]))
            if len(q) <= 15:
                continue
            for t in test:
                if q == t:
                    alertes.append((e["id"], 1.0, t))
                else:
                    sm = difflib.SequenceMatcher(None, q, t)
                    if sm.real_quick_ratio() >= SEUIL_SIMILARITE and sm.ratio() >= SEUIL_SIMILARITE:
                        alertes.append((e["id"], sm.ratio(), t))
    return alertes


def split_de(personnage):
    if personnage in TEST_CHARACTERS:
        return None
    return "val" if personnage in VAL_CHARACTERS else "train"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stats", action="store_true", help="statistiques sur tous les exemples, sans rien écrire")
    args = parser.parse_args()

    case, fiches = charger_affaire(ROOT / "cases" / "main_case")
    dialogues = charger_dialogues()
    statuts = Counter(d["statut"] for d in dialogues)
    relus = statuts["ok"] + statuts["rejete"]
    print(f"{len(dialogues)} exemples : {dict(statuts)}")
    if relus:
        print(f"taux de rejet : {statuts['rejete'] / relus:.0%} des exemples tranchés")
    if not args.stats:
        if not statuts["ok"]:
            sys.exit("Aucun exemple accepté (statut « ok ») : relire d'abord les dialogues avec data/relire.py.")
        if statuts["a_relire"]:
            print(f"ATTENTION : {statuts['a_relire']} exemple(s) pas encore relu(s), donc exclu(s) "
                  "(python data/relire.py --bilan)")

    gardes = dialogues if args.stats else [d for d in dialogues if d["statut"] == "ok"]
    erreurs = []

    # Message système reconstruit avec les fiches et les règles actuelles.
    perimes = 0
    for d in gardes:
        systeme = build_system_prompt(fiches[d["personnage"]], case, d["etat"])
        if d["messages"][0]["content"] != systeme:
            perimes += 1
        d["messages"] = [{"role": "system", "content": systeme}] + d["messages"][1:]
    if perimes:
        print(f"ATTENTION : {perimes} exemple(s) rédigé(s) avec une version antérieure d'une fiche ou des "
              "règles ; relancer `generate.py assembler` puis les relire.")

    # Découpage par personnage.
    for d in gardes:
        if split_de(d["personnage"]) != d["split"]:
            erreurs.append(f"{d['id']} : split « {d['split']} » incohérent avec src/config.py")
        if d["personnage"] in TEST_CHARACTERS:
            erreurs.append(f"{d['id']} : personnage de test dans les données")

    # Aucune question du jeu de test dans les données.
    alertes = verifier_fuite_test(gardes, questions_du_test())
    for ident, ratio, question in alertes:
        (erreurs.append if ratio == 1.0 else print)(
            f"{'' if ratio == 1.0 else 'ATTENTION : '}{ident} : question de test reprise ({ratio:.0%}) : « {question} »")

    # Longueurs.
    compter = compteur_tokens()
    trop_longs = set()
    if compter:
        longueurs = {d["id"]: compter(d["messages"]) for d in gardes}
        trop_longs = {i for i, n in longueurs.items() if n > MAX_LENGTH}
        valeurs = sorted(longueurs.values())
        if valeurs:
            print(f"tokens par exemple : min {valeurs[0]}, médiane {valeurs[len(valeurs) // 2]}, "
                  f"max {valeurs[-1]} (limite {MAX_LENGTH}) ; écartés car trop longs : {len(trop_longs)}")
    else:
        print("ATTENTION : transformers absent, longueurs non vérifiées")

    if args.stats:
        for cle in ("split", "personnage", "situation", "perte_sur"):
            print(f"{cle:10} {dict(sorted(Counter(d[cle] for d in gardes).items()))}")
        etats = Counter("pièce présentée" if "piece_presentee" in d["etat"] else
                        "après aveu" if d["etat"] else "tout verrouillé" for d in gardes)
        print(f"{'état':10} {dict(etats)}")
        tours = Counter(sum(m["role"] == "assistant" for m in d["messages"]) for d in gardes)
        print(f"{'tours':10} {dict(sorted(tours.items()))}")
    if erreurs:
        sys.exit("ERREURS, rien n'est écrit :\n  " + "\n  ".join(erreurs))
    if args.stats:
        return

    parts = {"train": [], "val": []}
    for d in gardes:
        if d["id"] not in trop_longs:
            parts[d["split"]].append({"id": d["id"], "personnage": d["personnage"],
                                      "situation": d["situation"], "perte_sur": d["perte_sur"],
                                      "messages": d["messages"]})
    for nom, rows in parts.items():
        random.Random(SEED).shuffle(rows)
        with open(DATA_DIR / f"{nom}.jsonl", "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"{nom}: {len(rows)} exemples")


if __name__ == "__main__":
    main()
