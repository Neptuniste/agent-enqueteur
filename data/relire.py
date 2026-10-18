"""Relecture humaine des dialogues (cahier des charges, §9.5).

Chaque exemple « a_relire » passe à « ok » ou à « rejete » ; la décision est enregistrée aussitôt.

    python data/relire.py rose_delorme     # relit les exemples à relire de ce personnage
    python data/relire.py --tous            # tous les personnages, l'un après l'autre
    python data/relire.py --bilan           # avancement et taux de rejet

Touches : o = ok, r = rejeter (avec un motif), c = corriger une réplique, f = afficher le message
système complet, s = passer, q = quitter.

Grille de validation (§9.5) : conforme à la fiche, ton respecté, aucun fait inventé, aucune fuite
de secret verrouillé, 2 à 5 phrases et une didascalie au plus, aucune donnée réelle.
Une correction est reportée dans data/raw/brut/ : un nouvel `assembler` la conserve.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data"))

import generate  # noqa: E402  (même dossier : contrôles automatiques)
from src.game_state import charger_affaire, texte_du_dossier  # noqa: E402


def lire(perso):
    chemin = RAW / f"{perso}.jsonl"
    return chemin, [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines() if l.strip()]


def ecrire(chemin, lignes):
    temporaire = chemin.with_suffix(".tmp")
    temporaire.write_text("".join(json.dumps(l, ensure_ascii=False) + "\n" for l in lignes), encoding="utf-8")
    temporaire.replace(chemin)  # écriture atomique : une coupure ne corrompt pas le fichier


def reporter_dans_brut(perso, ident, tour, texte):
    """La correction devient la source : `generate.py assembler` la reproduira."""
    for fichier in sorted((RAW / "brut").glob(f"{perso}*.json")):
        brut = json.loads(fichier.read_text(encoding="utf-8"))
        if ident in brut:
            brut[ident][tour - 1][1] = texte
            lignes = ",\n".join(f'"{k}": ' + json.dumps(v, ensure_ascii=False) for k, v in brut.items())
            fichier.write_text("{\n" + lignes + "\n}\n", encoding="utf-8")
            return


def afficher(e):
    etat = e["etat"]
    print("\n" + "=" * 90)
    print(f"{e['id']}  |  {e['situation']}  |  perte : {e['perte_sur']}")
    print(f"avoués : {etat.get('secrets_avoues', [])}  montrées : {etat.get('pieces_montrees', [])}  "
          f"pièce présentée : {etat.get('piece_presentee', '-')}")
    for niveau in ("bloquants", "remarques"):
        for msg in e["controles"][niveau]:
            print(f"  [{niveau}] {msg}")
    print("-" * 90)
    tour = 0
    for m in e["messages"][1:]:
        if m["role"] == "user":
            tour += 1
            print(f"\n[{tour}] INSPECTEUR : {m['content']}")
        else:
            print(f"    PERSONNAGE : {m['content']}")


def relire_personnage(perso, case, fiches, public):
    chemin, lignes = lire(perso)
    for e in lignes:
        if e["statut"] != "a_relire":
            continue
        afficher(e)
        while True:
            choix = input("\n[o]k  [r]ejeter  [c]orriger  [f]iche  [s]auter  [q]uitter > ").strip().lower()
            if choix == "o":
                e["statut"], e["motif"] = "ok", ""
            elif choix == "r":
                e["statut"], e["motif"] = "rejete", input("motif : ").strip() or "relecture"
            elif choix == "c":
                tour = int(input("numéro du tour à corriger : "))
                texte = input("nouvelle réplique du personnage : ").strip()
                reponses = [i for i, m in enumerate(e["messages"]) if m["role"] == "assistant"]
                e["messages"][reponses[tour - 1]]["content"] = texte
                tours = [[e["messages"][i - 1]["content"], e["messages"][i]["content"]] for i in reponses]
                exemple = {k: e[k] for k in ("etat", "situation")} | {"n_tours": len(tours)}
                bloquants, remarques = generate.controler(exemple, tours, fiches[perso], case, public)
                e["controles"] = {"bloquants": bloquants, "remarques": remarques}
                reporter_dans_brut(perso, e["id"], tour, texte)
                afficher(e)
                continue
            elif choix == "f":
                print("\n" + e["messages"][0]["content"])
                continue
            elif choix == "s":
                break
            elif choix == "q":
                ecrire(chemin, lignes)
                return False
            else:
                continue
            ecrire(chemin, lignes)
            break
    ecrire(chemin, lignes)
    return True


def bilan():
    total = Counter()
    for chemin in sorted(RAW.glob("*.jsonl")):
        _, lignes = lire(chemin.stem)
        c = Counter(l["statut"] for l in lignes)
        total.update(c)
        print(f"{chemin.stem:20} {dict(c)}")
    tranches = total["ok"] + total["rejete"]
    print(f"{'TOTAL':20} {dict(total)}" + (f"  | rejet : {total['rejete'] / tranches:.0%}" if tranches else ""))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("personnage", nargs="?")
    parser.add_argument("--tous", action="store_true")
    parser.add_argument("--bilan", action="store_true")
    args = parser.parse_args()
    if args.bilan:
        return bilan()
    case, fiches = charger_affaire(ROOT / "cases" / "main_case")
    public = texte_du_dossier(case, ROOT / "cases" / "main_case",
                              [p["id"] for p in case["pieces"] if p["disponible_au_depart"]])
    persos = sorted(p.stem for p in RAW.glob("*.jsonl")) if args.tous else [args.personnage]
    if persos == [None]:
        parser.error("indiquer un personnage, --tous ou --bilan")
    for perso in persos:
        if not relire_personnage(perso, case, fiches, public):
            break
    bilan()


if __name__ == "__main__":
    main()
