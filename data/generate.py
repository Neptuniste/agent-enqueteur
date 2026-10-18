"""Prépare et assemble les dialogues d'entraînement (cahier des charges, §9.3 à §9.6).

    python data/generate.py plan                  # tire le plan des exemples -> data/raw/plan.json
    python data/generate.py fiche rose_delorme    # message système exact + dialogues à écrire, état par état
    python data/generate.py assembler rose_delorme  # data/raw/brut/<perso>*.json -> data/raw/<perso>.jsonl

Les dialogues sont rédigés par un LLM « professeur » (ici Claude Opus 5.5 dans Claude Code)
d'après la sortie de `fiche` et les consignes de data/consignes_redaction.md, puis écrits dans
data/raw/brut/<perso>*.json (un ou plusieurs fichiers) sous la forme {"<id>": [["réplique du joueur", "réplique du personnage"], ...]}.
`assembler` construit le message système de chaque exemple avec prompt_builder (le même qu'à
l'inférence), applique les contrôles automatiques et écrit data/raw/<perso>.jsonl avec le statut
« a_relire » (ou « rejete » si un contrôle bloquant échoue). La relecture humaine se fait ensuite
avec data/relire.py.
"""

import argparse
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import SEED, TEST_CHARACTERS, VAL_CHARACTERS  # noqa: E402
from src.game_state import charger_affaire, secrets_ouverts_par, texte_du_dossier  # noqa: E402
from src.guard import detecter_fuites, normaliser  # noqa: E402
from src.prompt_builder import annonce_piece, build_system_prompt  # noqa: E402

DOSSIER_AFFAIRE = ROOT / "cases" / "main_case"
RAW = ROOT / "data" / "raw"
PLAN = RAW / "plan.json"

EXEMPLES_ENTRAINEMENT = 78   # par personnage d'entraînement (~450 + une petite marge pour les rejets)
EXEMPLES_VALIDATION = 72     # par personnage de validation (~70)

# Situations du §9.4 : part, nombre de tours possibles, pièce présentée au dernier tour ?
SITUATIONS = {
    "factuel":           (0.20, (1, 2), False),
    "alibi":             (0.10, (1, 2), False),
    "mensonge_maintenu": (0.10, (2, 3), False),
    "confrontation":     (0.15, (1, 2), True),
    "sans_rapport":      (0.05, (1, 2), True),
    "autre_personnage":  (0.10, (1, 2), False),
    "inconnu":           (0.15, (1, 2), False),
    "hors_perimetre":    (0.10, (1, 2), False),
    "memoire":           (0.05, (3, 4), False),
}
PART_APRES_AVEU = 0.25       # situations sans pièce : part jouée après un aveu (sinon tout verrouillé)
PART_REPRESENTATION = 0.15   # confrontations où la pièce a déjà été avouée (« déjà avoué »)
TAILLE_LOT = 6               # dialogues affichés ensemble par `fiche`

# Le personnage se présente comme une machine : bloquant. Il cite un terme moderne : à vérifier,
# sauf si le joueur vient de l'employer (« Une IA ? Qu'est-ce que c'est ? » est la bonne réaction).
HORS_ROLE = ["je suis une ia", "en tant qu'ia", "je suis un modèle", "modèle de langage",
             "assistant virtuel", "je suis un programme"]
TERMES_MODERNES = ["intelligence artificielle", " ia ", "chatbot", "prompt système", "programme"]
ANACHRONISMES = ["portable", "internet", "ordinateur", "e-mail", "smartphone", "texto", " ok ", "cool"]
DIDASCALIE = re.compile(r"\*\([^*]+\)\*")


# --- Plan -----------------------------------------------------------------------------------

def repartir(total, parts):
    """Répartit `total` selon des parts (méthode du plus fort reste)."""
    bruts = {k: total * p for k, p in parts.items()}
    nombres = {k: int(v) for k, v in bruts.items()}
    reste = total - sum(nombres.values())
    for k in sorted(bruts, key=lambda k: bruts[k] - nombres[k], reverse=True)[:reste]:
        nombres[k] += 1
    return nombres


def prerequis(case, fiches, perso_id):
    """Pour chaque secret du personnage : les secrets du même personnage qu'il faut avoir avoués avant.

    Une pièce débloquée seulement par un aveu de ce même personnage (la liasse de Rose, débloquée
    par son aveu du vestiaire) impose cet aveu d'abord. Sinon, aucun prérequis.
    """
    depart = {p["id"] for p in case["pieces"] if p["disponible_au_depart"]}
    debloquee_par = {}
    for pid, fiche in fiches.items():
        for s in fiche["secrets"]:
            for p in s["debloque"]:
                debloquee_par.setdefault(p, []).append((pid, s["id"]))
    resultat = {}
    for s in fiches[perso_id]["secrets"]:
        options = []
        for p in s["revele_si"]:
            sources = debloquee_par.get(p, [])
            if p in depart or any(pid != perso_id for pid, _ in sources):
                options = []
                break
            options.extend(sid for pid, sid in sources if pid == perso_id)
        resultat[s["id"]] = sorted(set(options))
    return resultat


def fermer(avoues, prereqs):
    """Ajoute les prérequis manquants à un ensemble de secrets avoués."""
    avoues = set(avoues)
    while True:
        manquants = {p for s in avoues for p in prereqs.get(s, [])} - avoues
        if not manquants:
            return avoues
        avoues |= manquants


def piece_pour(secret, avoues_avant, prereqs_pieces, rng):
    """Une pièce qui ouvre ce secret et dont les prérequis sont satisfaits."""
    possibles = [p for p in secret["revele_si"] if prereqs_pieces.get(p, set()) <= avoues_avant]
    return rng.choice(possibles or secret["revele_si"])


def etat_apres_aveux(fiche, avoues, prereqs_pieces, rng):
    """État d'un interrogatoire où ces secrets ont déjà été avoués, avec les pièces correspondantes."""
    secrets = {s["id"]: s for s in fiche["secrets"]}
    montrees, faits = [], set()
    for sid in [s["id"] for s in fiche["secrets"] if s["id"] in avoues]:
        p = piece_pour(secrets[sid], faits, prereqs_pieces, rng)
        if p not in montrees:
            montrees.append(p)
        faits.add(sid)
    # Une pièce montrée a fait avouer TOUS les secrets qu'elle ouvre (la liasse : sortie et vol).
    avoues = set(avoues) | {s["id"] for p in montrees for s in secrets_ouverts_par(fiche, p)}
    return {"secrets_avoues": sorted(avoues, key=list(secrets).index), "pieces_montrees": montrees}


def planifier_personnage(case, fiches, perso_id, total, rng):
    fiche = fiches[perso_id]
    avouables = [s for s in fiche["secrets"] if s["revele_si"]]
    prereqs = prerequis(case, fiches, perso_id)
    # Prérequis par pièce : la liasse demande l'aveu du vestiaire, etc.
    prereqs_pieces = {}
    for s in fiche["secrets"]:
        for p in s["debloque"]:
            prereqs_pieces.setdefault(p, set()).add(s["id"])
    sans_rapport = [p["id"] for p in case["pieces"] if not secrets_ouverts_par(fiche, p["id"])]

    # Ensembles d'aveux possibles : singletons et paires, fermés par les prérequis.
    candidats = {frozenset(fermer({s["id"]}, prereqs)) for s in avouables}
    candidats |= {frozenset(fermer({a["id"], b["id"]}, prereqs))
                  for i, a in enumerate(avouables) for b in avouables[i + 1:]}
    candidats = sorted(candidats, key=lambda c: (len(c), sorted(c)))

    exemples = []
    nombres = repartir(total, {k: v[0] for k, v in SITUATIONS.items()})
    for situation, nombre in nombres.items():
        _, (tmin, tmax), presente = SITUATIONS[situation]
        for i in range(nombre):
            n_tours = rng.randint(tmin, tmax)
            if situation == "confrontation":
                secret = avouables[i % len(avouables)]
                if rng.random() < PART_REPRESENTATION:
                    avoues = fermer({secret["id"]}, prereqs)
                    etat = etat_apres_aveux(fiche, avoues, prereqs_pieces, rng)
                    etat["piece_presentee"] = next(
                        (p for p in etat["pieces_montrees"] if p in secret["revele_si"]), secret["revele_si"][0])
                else:
                    avant = fermer(set(prereqs.get(secret["id"], [])), prereqs)
                    # Autres aveux déjà faits, sans jamais exiger celui qu'on va provoquer.
                    autres = [s["id"] for s in avouables if s["id"] != secret["id"] and s["id"] not in avant
                              and secret["id"] not in fermer({s["id"]}, prereqs)]
                    if autres and rng.random() < 0.3:
                        avant = fermer(avant | {rng.choice(autres)}, prereqs)
                    etat = etat_apres_aveux(fiche, avant, prereqs_pieces, rng)
                    if secret["id"] in etat["secrets_avoues"]:  # déjà ouvert par une pièce montrée
                        avant = fermer(set(prereqs.get(secret["id"], [])), prereqs)
                        etat = etat_apres_aveux(fiche, avant, prereqs_pieces, rng)
                    etat["piece_presentee"] = piece_pour(secret, avant, prereqs_pieces, rng)
            elif situation == "sans_rapport":
                avoues = set(rng.choice(candidats)) if rng.random() < 0.2 and candidats else set()
                etat = etat_apres_aveux(fiche, avoues, prereqs_pieces, rng)
                etat["piece_presentee"] = rng.choice(sans_rapport)
            else:
                avoues = set(rng.choice(candidats)) if rng.random() < PART_APRES_AVEU and candidats else set()
                etat = etat_apres_aveux(fiche, avoues, prereqs_pieces, rng)
            etat = {k: v for k, v in etat.items() if v}
            exemples.append({"situation": situation, "n_tours": n_tours, "etat": etat,
                             "perte_sur": "dernier" if presente and n_tours > 1 else "tous"})

    # Regroupe par état identique (même message système) et numérote.
    exemples.sort(key=lambda e: (json.dumps(e["etat"], sort_keys=True), e["situation"]))
    for i, e in enumerate(exemples, 1):
        e["id"] = f"{perso_id}-{i:03d}"
    return exemples


def construire_plan():
    case, fiches = charger_affaire(DOSSIER_AFFAIRE)
    rng = random.Random(SEED)
    plan = {}
    for perso_id in sorted(fiches):
        if perso_id in TEST_CHARACTERS:
            continue
        split = "val" if perso_id in VAL_CHARACTERS else "train"
        total = EXEMPLES_VALIDATION if split == "val" else EXEMPLES_ENTRAINEMENT
        plan[perso_id] = {"split": split,
                          "exemples": planifier_personnage(case, fiches, perso_id, total, rng)}
    return plan


def verifier_plan(plan):
    """Garde-fous : chaque état tiré doit être possible en jeu."""
    case, fiches = charger_affaire(DOSSIER_AFFAIRE)
    problemes = []
    for perso_id, bloc in plan.items():
        fiche = fiches[perso_id]
        prereqs = prerequis(case, fiches, perso_id)
        for e in bloc["exemples"]:
            avoues = set(e["etat"].get("secrets_avoues", []))
            montrees = e["etat"].get("pieces_montrees", [])
            piece = e["etat"].get("piece_presentee")
            for p in montrees:
                manquants = {s["id"] for s in secrets_ouverts_par(fiche, p)} - avoues
                if manquants:
                    problemes.append(f"{e['id']} : {p} montrée sans l'aveu de {sorted(manquants)}")
            for s in avoues:
                if not set(prereqs.get(s, [])) <= avoues:
                    problemes.append(f"{e['id']} : {s} avoué sans ses prérequis")
            ouverts = {s["id"] for s in secrets_ouverts_par(fiche, piece)} if piece else set()
            if e["situation"] == "confrontation" and not ouverts:
                problemes.append(f"{e['id']} : confrontation avec une pièce qui n'ouvre rien")
            if e["situation"] == "sans_rapport" and ouverts:
                problemes.append(f"{e['id']} : pièce « sans rapport » qui ouvre un secret")
    return problemes


def commande_plan(_args):
    plan = construire_plan()
    problemes = verifier_plan(plan)
    if problemes:
        sys.exit("Plan incohérent :\n  " + "\n  ".join(problemes))
    RAW.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    total = 0
    for perso_id, bloc in plan.items():
        ex = bloc["exemples"]
        total += len(ex)
        etats = Counter("piece" if "piece_presentee" in e["etat"] else
                        "aveu" if e["etat"] else "verrouille" for e in ex)
        print(f"{perso_id:20} {bloc['split']:5} {len(ex):3} exemples, "
              f"{len({json.dumps(e['etat'], sort_keys=True) for e in ex}):2} états | {dict(etats)}")
    print(f"total : {total} exemples -> {PLAN.relative_to(ROOT)}")


# --- Fiche de rédaction ------------------------------------------------------------------------

def charger_plan():
    if not PLAN.exists():
        sys.exit("Plan absent : lancer d'abord `python data/generate.py plan`.")
    return json.loads(PLAN.read_text(encoding="utf-8"))


def commande_fiche(args):
    case, fiches = charger_affaire(DOSSIER_AFFAIRE)
    pieces = {p["id"]: p for p in case["pieces"]}
    plan = charger_plan()
    if args.personnage not in plan:
        sys.exit(f"{args.personnage} n'est pas dans le plan (personnage de test, ou plan à refaire).")
    exemples = plan[args.personnage]["exemples"]
    fiche = fiches[args.personnage]
    groupes = {}
    for e in exemples:
        groupes.setdefault(json.dumps(e["etat"], sort_keys=True), []).append(e)
    reference = build_system_prompt(fiche, case, {}).split("\n\n")
    if args.compact:
        print("FICHE COMPLÈTE AU DÉBUT DE L'INTERROGATOIRE (les états ci-dessous n'affichent que ce qui change)")
        print("\n\n".join(reference[2:]))
    for cle, groupe in groupes.items():
        etat = json.loads(cle)
        print("=" * 100)
        print(f"ÉTAT {etat or 'début, tout verrouillé'}")
        print("-" * 100)
        sections = build_system_prompt(fiche, case, etat).split("\n\n")
        if args.compact:
            sections = [s for s in sections if s not in reference] or ["(identique au début)"]
            print("\n\n".join(sections))
        else:
            print("\n\n".join(sections[2:]))
        if "piece_presentee" in etat:
            print(f"\nANNONCE EXACTE DU DERNIER TOUR : {annonce_piece(pieces[etat['piece_presentee']])}")
        print("-" * 100)
        for e in groupe:
            print(f"{e['id']}  {e['situation']:18} {e['n_tours']} tour(s)  perte : {e['perte_sur']}")


# --- Assemblage et contrôles -------------------------------------------------------------------

def phrases(texte):
    """Nombre de phrases d'une réplique, didascalies exclues (« M. Delorme » ne coupe pas la phrase)."""
    texte = re.sub(r"\bM\.\s", "M ", DIDASCALIE.sub(" ", texte))
    return len([p for p in re.split(r"(?<=[.!?…])\s+", texte.strip()) if re.search(r"\w", p)])


def controler(exemple, tours, fiche, case, public):
    """Contrôles automatiques. Renvoie (bloquants, remarques)."""
    pieces = {p["id"]: p for p in case["pieces"]}
    etat = exemple["etat"]
    bloquants, remarques = [], []
    if len(tours) != exemple["n_tours"]:
        bloquants.append(f"{len(tours)} tour(s) au lieu de {exemple['n_tours']}")
    for i, tour in enumerate(tours, 1):
        if not (isinstance(tour, list) and len(tour) == 2 and all(isinstance(t, str) and t.strip() for t in tour)):
            bloquants.append(f"tour {i} mal formé")
            return bloquants, remarques
    piece_id = etat.get("piece_presentee")
    annonces = [i for i, (joueur, _) in enumerate(tours, 1) if joueur.startswith("*(L'inspecteur vous montre")]
    if piece_id:
        attendue = annonce_piece(pieces[piece_id])
        if not tours[-1][0].startswith(attendue):
            bloquants.append(f"le dernier tour ne commence pas par l'annonce exacte : {attendue}")
        if annonces != [len(tours)]:
            bloquants.append("une annonce de pièce apparaît avant le dernier tour")
    elif annonces:
        bloquants.append("annonce de pièce dans une situation sans pièce")

    avoues = set(etat.get("secrets_avoues", []))
    ouverts = {s["id"] for s in secrets_ouverts_par(fiche, piece_id)} if piece_id else set()
    connu = public + " " + " ".join(pieces[p]["description"] for p in etat.get("pieces_montrees", []))
    for i, (joueur, reponse) in enumerate(tours, 1):
        dernier = i == len(tours)
        connu += " " + joueur
        if dernier and piece_id:
            connu += " " + pieces[piece_id]["description"]
        fuites = detecter_fuites(reponse, fiche, avoues | (ouverts if dernier else set()), connu)
        if fuites:
            bloquants.append(f"tour {i} : fuite d'un secret verrouillé ({', '.join(fuites)})")
        bas = " " + normaliser(reponse) + " "
        if any(m in bas for m in HORS_ROLE):
            bloquants.append(f"tour {i} : sortie du rôle")
        modernes = [m.strip() for m in TERMES_MODERNES if m in bas and m not in " " + normaliser(joueur) + " "]
        if modernes:
            remarques.append(f"tour {i} : terme moderne ({', '.join(modernes)})")
        n = phrases(reponse)
        if not 2 <= n <= 5:
            remarques.append(f"tour {i} : {n} phrase(s) (2 à 5 attendues)")
        if len(DIDASCALIE.findall(reponse)) > 1:
            remarques.append(f"tour {i} : plus d'une didascalie")
        if "*" in DIDASCALIE.sub("", reponse):
            remarques.append(f"tour {i} : astérisque hors didascalie")
        if any(m in bas for m in ANACHRONISMES):
            remarques.append(f"tour {i} : anachronisme possible")
        if len(reponse.split()) > 110:
            remarques.append(f"tour {i} : réplique longue ({len(reponse.split())} mots)")
    return bloquants, remarques


def commande_assembler(args):
    case, fiches = charger_affaire(DOSSIER_AFFAIRE)
    perso_id = args.personnage
    fiche = fiches[perso_id]
    bloc = charger_plan()[perso_id]
    brut = {}
    for fichier in sorted((RAW / "brut").glob(f"{perso_id}*.json")):  # rose_delorme.json, rose_delorme_2.json...
        partie = json.loads(fichier.read_text(encoding="utf-8"))
        doublons = set(partie) & set(brut)
        if doublons:
            sys.exit(f"{fichier.name} : identifiants déjà rédigés ailleurs : {sorted(doublons)}")
        brut.update(partie)
    inconnus = set(brut) - {e["id"] for e in bloc["exemples"]}
    if inconnus:
        sys.exit(f"identifiants absents du plan : {sorted(inconnus)}")
    depart = [p["id"] for p in case["pieces"] if p["disponible_au_depart"]]
    public = texte_du_dossier(case, DOSSIER_AFFAIRE, depart)

    sortie = RAW / f"{perso_id}.jsonl"
    anciens = {}
    if sortie.exists():
        for ligne in sortie.read_text(encoding="utf-8").splitlines():
            if ligne.strip():
                e = json.loads(ligne)
                anciens[e["id"]] = e

    lignes, compte, premieres = [], Counter(), Counter()
    for exemple in bloc["exemples"]:
        if exemple["id"] not in brut:
            compte["non rédigé"] += 1
            continue
        tours = brut[exemple["id"]]
        bloquants, remarques = controler(exemple, tours, fiche, case, public)
        messages = [{"role": "system", "content": build_system_prompt(fiche, case, exemple["etat"])}]
        bien_formes = bool(tours) and all(isinstance(t, list) and len(t) == 2 for t in tours)
        for joueur, reponse in tours if bien_formes else []:
            messages += [{"role": "user", "content": joueur}, {"role": "assistant", "content": reponse}]
        if bien_formes:
            premieres[normaliser(tours[0][0])] += 1
        ligne = {"id": exemple["id"], "personnage": perso_id, "split": bloc["split"],
                 "situation": exemple["situation"], "etat": exemple["etat"],
                 "perte_sur": exemple["perte_sur"], "messages": messages,
                 "controles": {"bloquants": bloquants, "remarques": remarques},
                 "statut": "rejete" if bloquants else "a_relire",
                 "motif": "contrôle automatique" if bloquants else ""}
        ancien = anciens.get(exemple["id"])
        if ancien and ancien["messages"] == messages and ancien["statut"] in ("ok", "rejete") and not bloquants:
            ligne["statut"], ligne["motif"] = ancien["statut"], ancien.get("motif", "")  # décision humaine conservée
        compte[ligne["statut"]] += 1
        lignes.append(ligne)
    doublons = [q for q, n in premieres.items() if n > 1 and q]
    if doublons:
        print(f"ATTENTION : {len(doublons)} première(s) question(s) répétée(s) : {doublons[:3]}")
    sortie.write_text("".join(json.dumps(l, ensure_ascii=False) + "\n" for l in lignes), encoding="utf-8")
    print(f"{perso_id} : {dict(compte)} -> {sortie.relative_to(ROOT)}")
    for l in lignes:
        if l["controles"]["bloquants"] or l["controles"]["remarques"]:
            print(f"  {l['id']} {l['situation']:18} " + " | ".join(l["controles"]["bloquants"] + l["controles"]["remarques"]))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sous = parser.add_subparsers(dest="commande", required=True)
    sous.add_parser("plan").set_defaults(fonction=commande_plan)
    p = sous.add_parser("fiche")
    p.add_argument("personnage")
    p.add_argument("--compact", action="store_true", help="n'affiche que ce qui change d'un état à l'autre")
    p.set_defaults(fonction=commande_fiche)
    p = sous.add_parser("assembler")
    p.add_argument("personnage")
    p.set_defaults(fonction=commande_assembler)
    args = parser.parse_args()
    args.fonction(args)


if __name__ == "__main__":
    main()
