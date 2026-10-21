"""Notation à l'aveugle au clavier (cahier des charges, §11), plus rapide qu'Excel.

    python eval/noter.py A            # premier notateur : remplit results/notes_A.csv
    python eval/noter.py B            # second notateur, sur sa propre feuille
    python eval/noter.py A --bilan    # avancement
    python eval/noter.py A --tout     # repasser sur toutes les réponses, pour corriger

Pour chaque réponse, taper une seule ligne : un chiffre (0, 1 ou 2) par critère affiché, dans l'ordre,
puis éventuellement un commentaire. Exemple : « 2122 trop long ». Autres touches : g = revoir la grille,
s = passer, q = quitter. La feuille est enregistrée après chaque réponse ; une relance reprend où l'on
s'était arrêté. La version notée (baseline ou LoRA) n'est jamais affichée.
"""

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval.evaluate import CRITERES, NON_APPLICABLE, lire_feuille  # noqa: E402

GRILLE = {  # eval/grille_evaluation.md, en une ligne par critère
    "pertinence": "cohérent avec la fiche : 0 ne répond pas, 1 partiellement, 2 clairement",
    "role_format": "personnage, 2 à 5 phrases, 1 didascalie au plus : 0 sort du rôle, 1 ton incohérent ou trop long, 2 respectés",
    "historique": "cohérent avec les tours précédents : 0 se contredit, 1 ignore l'historique, 2 cohérent",
    "hors_perimetre": "reste en 1928 : 0 sort du jeu ou révèle, 1 reste flou, 2 reste dans le rôle et recadre",
    "invention": "rien hors de la fiche, aucun secret trop tôt : 0 invente, 1 détail anodin, 2 aucune invention",
    "bonus_mensonge": "tient sa version sans preuve : 0 avoue, 1 hésite, 2 tient",
    "bonus_mise_en_scene": "voix et didascalie : 0 plat ou anachronique, 1 correct, 2 vivant",
}


def a_noter(ligne):
    return [c for c in CRITERES if (ligne.get(c) or "").strip() != NON_APPLICABLE]


def complete(ligne):
    return all((ligne.get(c) or "").strip() for c in a_noter(ligne))


def ecrire(chemin, lignes):
    temporaire = chemin.with_suffix(".tmp")
    with open(temporaire, "w", encoding="utf-8-sig", newline="") as f:  # s'ouvre tel quel dans Excel
        w = csv.DictWriter(f, fieldnames=list(lignes[0]), delimiter=";")
        w.writeheader()
        w.writerows(lignes)
    temporaire.replace(chemin)  # écriture atomique : une coupure ne corrompt pas la feuille


def afficher(ligne, rang, total):
    print("\n" + "=" * 90)
    print(f"Réponse {rang}/{total}  |  {ligne['code']}  |  {ligne['personnage']}  |  {ligne['type']}")
    print(f"Attendu : {ligne['attendu']}")
    print("-" * 90)
    print(ligne["transcription"].strip())
    print("-" * 90)
    criteres = a_noter(ligne)
    for i, c in enumerate(criteres, 1):
        actuelle = (ligne.get(c) or "").strip()
        print(f"  {i}. {c:20} {GRILLE[c]}" + (f"   [actuelle : {actuelle}]" if actuelle else ""))
    return criteres


def bilan(lignes):
    faites = sum(complete(l) for l in lignes)
    return f"{faites}/{len(lignes)} réponses notées"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("feuille", help="A, B, ou le chemin d'une feuille CSV")
    parser.add_argument("--bilan", action="store_true", help="afficher l'avancement")
    parser.add_argument("--tout", action="store_true", help="repasser aussi sur les réponses déjà notées")
    args = parser.parse_args()
    chemin = (ROOT / "results" / f"notes_{args.feuille.upper()}.csv") if len(args.feuille) == 1 else Path(args.feuille)
    if not chemin.exists():
        sys.exit(f"Feuille introuvable : {chemin}")
    lignes = lire_feuille(chemin)
    if args.bilan:
        return print(f"{chemin.name} : {bilan(lignes)}")

    rangs = [i for i, l in enumerate(lignes) if args.tout or not complete(l)]
    for rang, i in enumerate(rangs, 1):
        ligne = lignes[i]
        criteres = afficher(ligne, rang, len(rangs))
        while True:
            invite = f"\n{len(criteres)} chiffre(s) + commentaire facultatif"
            saisie = input(invite + (" (Entrée : garder)" if complete(ligne) else "") + ", g, s, q > ").strip()
            if saisie.lower() == "q":
                ecrire(chemin, lignes)
                return print(f"\nEnregistré. {bilan(lignes)}. Relancer la même commande pour reprendre.")
            if saisie.lower() == "s" or (saisie == "" and complete(ligne)):
                break
            if saisie.lower() == "g":
                for c in CRITERES:
                    print(f"  {c:20} {GRILLE[c]}")
                continue
            chiffres, _, commentaire = saisie.partition(" ")
            if len(chiffres) != len(criteres) or any(ch not in "012" for ch in chiffres):
                print(f"Il faut exactement {len(criteres)} chiffre(s), chacun 0, 1 ou 2 (exemple : {'2' * len(criteres)}).")
                continue
            for c, ch in zip(criteres, chiffres):
                ligne[c] = ch
            if commentaire.strip():
                ligne["commentaire"] = commentaire.strip()
            ecrire(chemin, lignes)
            break
    ecrire(chemin, lignes)
    print(f"\nTerminé : {bilan(lignes)} dans {chemin.name}.")


if __name__ == "__main__":
    main()
