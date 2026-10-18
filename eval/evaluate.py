"""Évaluation avant/après adaptation (cahier des charges, §11).

    python eval/evaluate.py verifier                                      # contrôle du jeu de test
    python eval/evaluate.py generer --version baseline
    python eval/evaluate.py generer --version lora --adaptateur adapter   # ou un dépôt Hugging Face
    python eval/evaluate.py auto                                          # métriques automatiques seules
    python eval/evaluate.py feuille                                       # feuille de notation à l'aveugle
    python eval/evaluate.py agreger [notes_A.csv notes_B.csv]             # une fois les notes saisies

Les versions répondent aux mêmes requêtes de data/test.jsonl, avec les mêmes réglages et la même graine
par requête. Le filtre de sortie est coupé : on évalue le modèle seul. Pour une requête à un tour, les
tirages sont générés en un seul appel : le premier est noté à la main, tous servent aux métriques
automatiques (fuite, aveu, longueur). Les scénarios sont joués tour par tour, chaque version gardant son
propre historique.
"""

import argparse
import csv
import json
import random
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import GENERATION_KWARGS, MODEL_NAME, SEED, TEST_CHARACTERS, VAL_CHARACTERS  # noqa: E402
from src.game_state import charger_affaire, secrets_ouverts_par, texte_du_dossier  # noqa: E402
from src.guard import compter_didascalies, compter_phrases, detecter_fuites, normaliser, sort_du_role  # noqa: E402
from src.prompt_builder import annonce_piece, build_system_prompt  # noqa: E402

AFFAIRE = ROOT / "cases" / "main_case"
TEST = ROOT / "data" / "test.jsonl"
RESULTATS = ROOT / "results"
TYPES = ["factuel", "alibi", "mensonge_maintenu", "confrontation", "sans_rapport",
         "autre_personnage", "inconnu", "hors_perimetre", "memoire"]  # §9.4
CRITERES = ["pertinence", "role_format", "historique", "hors_perimetre", "invention",
            "bonus_mensonge", "bonus_mise_en_scene"]  # grille du §11, notes de 0 à 2
PRINCIPAUX = CRITERES[:5]
NON_APPLICABLE = "-"
GROUPES = {"oui": "personnages vus", "non": "personnage jamais vu", "validation": "personnage de validation"}
COURTS = {"personnages vus": "vus", "personnage jamais vu": "jamais vu", "personnage de validation": "validation"}


def charger_tests():
    return [json.loads(l) for l in TEST.read_text(encoding="utf-8").splitlines() if l.strip()]


def criteres_applicables(item):
    """Critères à noter pour cette requête ; les autres sont marqués « - » sur la feuille."""
    ty = item["type"]
    exclus = set()
    if ty != "scenario" and not item.get("historique"):
        exclus.add("historique")
    if ty not in ("hors_perimetre", "sans_rapport", "scenario"):
        exclus.add("hors_perimetre")
    if ty not in ("alibi", "mensonge_maintenu", "memoire", "scenario"):
        exclus.add("bonus_mensonge")
    return [c for c in CRITERES if c not in exclus]


def verifier_tests(tests, case, fiches):
    """Le jeu de test respecte-t-il le §11 et l'affaire ? Renvoie la liste des problèmes."""
    pieces = {p["id"]: p for p in case["pieces"]}
    problemes = []
    if len({t["id"] for t in tests}) != len(tests):
        problemes.append("identifiants en double")
    for t in tests:
        fiche = fiches.get(t["personnage"])
        if fiche is None:
            problemes.append(f"{t['id']} : personnage inconnu {t['personnage']}")
            continue
        vu = ("non" if t["personnage"] in TEST_CHARACTERS
              else "validation" if t["personnage"] in VAL_CHARACTERS else "oui")
        if t["vu"] != vu:
            problemes.append(f"{t['id']} : vu = {t['vu']}, mais le découpage donne {vu}")
        if t["type"] == "scenario":
            for k, tour in enumerate(t["tours"], 1):
                if tour.get("piece") and tour["piece"] not in pieces:
                    problemes.append(f"{t['id']} tour {k} : pièce inconnue {tour['piece']}")
                if tour["question"].lstrip().startswith("*(L'inspecteur"):
                    problemes.append(f"{t['id']} tour {k} : annonce déjà écrite (l'évaluation l'ajoute)")
            continue
        if t["type"] not in TYPES:
            problemes.append(f"{t['id']} : type inconnu {t['type']}")
        etat = t["etat"]
        secrets = {s["id"] for s in fiche["secrets"]}
        problemes += [f"{t['id']} : secret inconnu {s}" for s in etat.get("secrets_avoues", []) if s not in secrets]
        problemes += [f"{t['id']} : pièce inconnue {p}" for p in etat.get("pieces_montrees", []) if p not in pieces]
        piece, ouverts = etat.get("piece_presentee"), []
        if piece:
            if piece not in pieces:
                problemes.append(f"{t['id']} : pièce inconnue {piece}")
                continue
            if not t["question"].startswith(annonce_piece(pieces[piece])):
                problemes.append(f"{t['id']} : la question ne commence pas par l'annonce de la pièce")
            ouverts = secrets_ouverts_par(fiche, piece)
        if t["type"] == "confrontation" and not ouverts:
            problemes.append(f"{t['id']} : confrontation, mais la pièce n'ouvre aucun secret")
        if t["type"] == "sans_rapport" and ouverts:
            problemes.append(f"{t['id']} : pièce « sans rapport » qui ouvre un secret")
        if (t["type"] == "confrontation") != bool(t.get("mots_attendus")):
            problemes.append(f"{t['id']} : mots_attendus réservés aux confrontations, et obligatoires pour elles")
        elif t.get("mots_attendus") and len(t["mots_attendus"]) < 2:
            problemes.append(f"{t['id']} : au moins 2 mots_attendus")
    simples = Counter(t["type"] for t in tests if t["type"] != "scenario")
    problemes += [f"type « {ty} » : {simples[ty]} requête(s), 2 au moins" for ty in TYPES if simples[ty] < 2]
    if simples["hors_perimetre"] < 4:
        problemes.append("hors périmètre : 2 requêtes de plus que le minimum, soit 4")
    scenarios = [t for t in tests if t["type"] == "scenario"]
    if len(scenarios) < 4 or sum(len(s["tours"]) >= 10 for s in scenarios) < 2:
        problemes.append("4 scénarios au moins, dont 2 de 10 tours")
    if len(tests) < 24:
        problemes.append(f"{len(tests)} requêtes, 24 au moins")
    if sum(t["vu"] == "non" for t in tests) * 3 < len(tests):
        problemes.append("moins d'un tiers des requêtes sur le personnage jamais vu")
    return problemes


# --- Génération -----------------------------------------------------------------------------------

def deja_connu(case, montrees, questions):
    """Ce que le joueur sait déjà : dossier de départ, pièces montrées et ses propres questions."""
    initiales = [p["id"] for p in case["pieces"] if p["disponible_au_depart"]]
    pieces = initiales + [p for p in montrees if p not in initiales]
    return "\n".join([texte_du_dossier(case, AFFAIRE, pieces), *questions])


def contient(texte_normalise, mot):
    """Le mot apparaît en début de mot (« fournisseur » trouve aussi « fournisseurs »)."""
    return re.search(r"(?<!\w)" + re.escape(normaliser(mot)), texte_normalise) is not None


def metriques(reponse, fiche, secrets_avoues, connu, mots_attendus=None, tokenizer=None):
    """Métriques automatiques d'une réponse (§11)."""
    m = {"fuites": detecter_fuites(reponse, fiche, secrets_avoues, connu),
         "phrases": compter_phrases(reponse),
         "didascalies": compter_didascalies(reponse),
         "hors_role": sort_du_role(reponse)}
    if tokenizer is not None:
        m["tokens"] = len(tokenizer(reponse, add_special_tokens=False)["input_ids"])
    if mots_attendus:
        bas = normaliser(reponse)
        m["aveu"] = sum(contient(bas, mot) for mot in mots_attendus) >= 2
    return m


def jouer_simple(item, model, tokenizer, case, fiches, graine, tirages):
    from src.llm import construire_messages, generer_tirages
    fiche, etat = fiches[item["personnage"]], item["etat"]
    piece = etat.get("piece_presentee")
    avoues = set(etat.get("secrets_avoues", []))
    if piece:  # la pièce fait avouer : ses mots ne sont plus une fuite
        avoues |= {s["id"] for s in secrets_ouverts_par(fiche, piece)}
    montrees = etat.get("pieces_montrees", []) + ([piece] if piece else [])
    questions = [m["content"] for m in item["historique"] if m["role"] == "user"] + [item["question"]]
    connu = deja_connu(case, montrees, questions)
    messages = construire_messages(build_system_prompt(fiche, case, etat), item["historique"],
                                   item["question"], tokenizer)
    textes = generer_tirages(model, tokenizer, messages, tirages, graine=graine)
    return [{"texte": t, **metriques(t, fiche, avoues, connu, item.get("mots_attendus"), tokenizer)}
            for t in textes]


def jouer_scenario(item, model, tokenizer, case, fiches, graine, mode="verrouille"):
    """Les questions sont écrites à l'avance ; l'état du jeu et l'historique suivent les réponses.

    mode : « verrouille » (prompt B, celui du jeu) ou « complet » (prompt A, comparé en partie 3).
    """
    from src.llm import construire_messages, generer_tirages
    fiche = fiches[item["personnage"]]
    pieces = {p["id"]: p for p in case["pieces"]}
    avoues, montrees, questions, historique, tours = [], [], [], [], []
    for i, tour in enumerate(item["tours"]):
        piece = tour.get("piece")
        question = f"{annonce_piece(pieces[piece])} {tour['question']}" if piece else tour["question"]
        # comme GameState.presenter : l'état du tour est pris AVANT la mise à jour
        etat = {"secrets_avoues": list(avoues), "pieces_montrees": list(montrees), "piece_presentee": piece}
        messages = construire_messages(build_system_prompt(fiche, case, etat, mode=mode), historique, question,
                                       tokenizer)
        if piece:
            avoues += [s["id"] for s in secrets_ouverts_par(fiche, piece) if s["id"] not in avoues]
            montrees += [piece] if piece not in montrees else []
        questions.append(question)
        texte = generer_tirages(model, tokenizer, messages, 1, graine=graine + i)[0]
        tours.append({"question": question, "texte": texte,
                      **metriques(texte, fiche, set(avoues), deja_connu(case, montrees, questions), None, tokenizer)})
        historique += [{"role": "user", "content": question}, {"role": "assistant", "content": texte}]
    return tours


def generer_version(model, tokenizer, version, dossier=RESULTATS, tirages=5, ids=None, infos=None):
    """Fait répondre un modèle déjà chargé à tout le jeu de test (ou aux requêtes ids).

    Écrit eval_<version>.jsonl et eval_<version>.json (réglages, durée) dans dossier.
    Dans le notebook, la baseline est le même modèle sous `with model.disable_adapter():`.
    """
    case, fiches = charger_affaire(AFFAIRE)
    tests = charger_tests()
    problemes = verifier_tests(tests, case, fiches)
    if problemes:
        raise ValueError("Jeu de test invalide :\n  " + "\n  ".join(problemes))
    selection = [t for t in tests if not ids or t["id"] in ids]
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    sortie = dossier / f"eval_{version}.jsonl"
    debut = time.perf_counter()
    with open(sortie, "w", encoding="utf-8") as f:
        for n, item in enumerate(selection, 1):
            graine = SEED + 1000 * tests.index(item)  # même graine pour toutes les versions
            if item["type"] == "scenario":
                resultat = {"tours": jouer_scenario(item, model, tokenizer, case, fiches, graine)}
            else:
                resultat = {"reponses": jouer_simple(item, model, tokenizer, case, fiches, graine, tirages)}
            f.write(json.dumps({**item, "version": version, **resultat}, ensure_ascii=False) + "\n")
            f.flush()
            print(f"[{n}/{len(selection)}] {item['id']} ({item['personnage']}, {item['type']}) "
                  f"{time.perf_counter() - debut:.0f} s")
    meta = {"version": version, **(infos or {}), "tirages": tirages, "reglages": GENERATION_KWARGS,
            "requetes": len(selection), "graine": SEED, "duree_s": round(time.perf_counter() - debut),
            "date": time.strftime("%Y-%m-%d %H:%M")}
    (dossier / f"eval_{version}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return sortie


def commande_generer(args):
    from src.llm import charger_modele
    case, fiches = charger_affaire(AFFAIRE)
    problemes = verifier_tests(charger_tests(), case, fiches)
    if problemes:  # avant de charger le modèle
        sys.exit("Jeu de test invalide :\n  " + "\n  ".join(problemes))
    modele = args.modele or MODEL_NAME
    model, tokenizer = charger_modele(modele, adaptateur=args.adaptateur)
    sortie = generer_version(model, tokenizer, args.version, args.resultats, args.tirages,
                             args.ids.split(",") if args.ids else None,
                             {"modele": modele, "adaptateur": args.adaptateur})
    print(f"-> {sortie}")


# --- Notation à l'aveugle -------------------------------------------------------------------------

def charger_resultats(dossier):
    """Résultats de chaque version : {version: [requêtes]}, la baseline en premier."""
    versions = {chemin.stem[len("eval_"):]: [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines() if l.strip()]
                for chemin in Path(dossier).glob("eval_*.jsonl")}
    return dict(sorted(versions.items(), key=lambda kv: (kv[0] != "baseline", kv[0])))


def transcrire(resultat, markdown=False):
    """Texte à noter : la question et le premier tirage, ou tout le scénario."""
    gras = (lambda s: f"**{s}**") if markdown else (lambda s: s)
    saut = "\n\n" if markdown else "\n"
    if "tours" in resultat:
        return saut.join(f"[{i}] {gras('INSPECTEUR')} : {t['question']}{saut}{gras('PERSONNAGE')} : {t['texte']}"
                         for i, t in enumerate(resultat["tours"], 1))
    avant = [f"{gras('INSPECTEUR' if m['role'] == 'user' else 'PERSONNAGE')} (avant) : {m['content']}"
             for m in resultat["historique"]]
    return saut.join(avant + [f"{gras('INSPECTEUR')} : {resultat['question']}",
                              f"{gras('PERSONNAGE')} : {resultat['reponses'][0]['texte']}"])


def commande_feuille(args):
    dossier = Path(args.resultats)
    versions = charger_resultats(dossier)
    if len(versions) < 2:
        sys.exit("Il faut au moins deux fichiers eval_<version>.jsonl (baseline et lora).")
    feuille, cles_chemin = dossier / "notation_aveugle.csv", dossier / "notation_cles.json"
    if feuille.exists() and not args.ecraser:
        sys.exit(f"{feuille} existe déjà (des notes seraient perdues) : --ecraser pour la refaire.")
    rng = random.Random(SEED)
    lignes, cles = [], {}
    for version, resultats in versions.items():
        for r in resultats:
            code = f"R{rng.randrange(10**5, 10**6)}"
            while code in cles:
                code = f"R{rng.randrange(10**5, 10**6)}"
            cles[code] = version
            applicables = criteres_applicables(r)
            lignes.append({"code": code, "id": r["id"], "personnage": r["personnage"], "type": r["type"],
                           "attendu": r["attendu"], "transcription": transcrire(r),
                           **{c: "" if c in applicables else NON_APPLICABLE for c in CRITERES}, "commentaire": ""})
    rng.shuffle(lignes)  # ordre mélangé, version masquée
    with open(feuille, "w", encoding="utf-8-sig", newline="") as f:  # s'ouvre tel quel dans Excel
        w = csv.DictWriter(f, fieldnames=list(lignes[0]), delimiter=";")
        w.writeheader()
        w.writerows(lignes)
    resultats = {(v, r["id"]): r for v, rs in versions.items() for r in rs}
    md = ["# Transcriptions à noter\n", "Notes de 0 à 2 dans la feuille CSV (grille : eval/grille_evaluation.md). "
          "« - » : critère sans objet pour cette requête.\n"]
    for ligne in lignes:
        r = resultats[(cles[ligne["code"]], ligne["id"])]
        md += [f"## {ligne['code']} – {ligne['id']} ({ligne['personnage']}, {ligne['type']})\n",
               f"*Attendu : {ligne['attendu']}*\n", transcrire(r, markdown=True) + "\n"]
    (dossier / "notation_transcriptions.md").write_text("\n".join(md), encoding="utf-8")
    cles_chemin.write_text(json.dumps(cles, indent=1), encoding="utf-8")
    print(f"{len(lignes)} lignes -> {feuille} (lecture confortable : notation_transcriptions.md).")
    print(f"Pour un 2ᵉ notateur, copier la feuille vierge. Ne pas ouvrir {cles_chemin.name} avant la fin.")


def lire_note(cellule, ou):
    """Note saisie (0 à 2, virgule décimale acceptée), ou None si vide ou sans objet."""
    cellule = (cellule or "").strip()
    if cellule in ("", NON_APPLICABLE):
        return None
    valeur = float(cellule.replace(",", "."))
    if not 0 <= valeur <= 2:
        raise ValueError(f"{ou} : note {cellule} hors de l'échelle 0 à 2")
    return valeur


def notes_humaines(feuilles, cles, tests):
    """Notes moyennes par code et critère (moyenne des notateurs), taux d'accord et cases oubliées."""
    par_case = defaultdict(list)
    infos, oublis = {}, Counter()
    for feuille in feuilles:
        with open(feuille, encoding="utf-8-sig") as f:
            for ligne in csv.DictReader(f, delimiter=";"):
                code = ligne["code"]
                infos[code] = {"id": ligne["id"], "version": cles[code], "type": ligne["type"],
                               "personnage": ligne["personnage"], "groupe": GROUPES[tests[ligne["id"]]["vu"]]}
                for c in CRITERES:
                    if ligne[c].strip() == "":
                        oublis[feuille.name] += 1
                    note = lire_note(ligne[c], f"{feuille.name}, {code}, {c}")
                    if note is not None:
                        par_case[(code, c)].append(note)
    doubles = [v for v in par_case.values() if len(v) >= 2]
    accord = (sum(len(set(v)) == 1 for v in doubles), len(doubles))
    moyennes = {k: sum(v) / len(v) for k, v in par_case.items()}
    return moyennes, infos, accord, oublis


def moyenne(valeurs):
    return sum(valeurs) / len(valeurs) if valeurs else None


def fmt(x, pourcent=False):
    if x is None:
        return "–"
    return f"{x:.0%}" if pourcent else f"{x:.2f}"


def tableau_humain(moyennes, infos, accord, oublis, ordre):
    def score(version, critere, groupe=None):
        return moyenne([n for (code, c), n in moyennes.items() if c == critere and infos[code]["version"] == version
                        and (groupe is None or infos[code]["groupe"] == groupe)])

    entete = ["| Critère | " + " | ".join(ordre) + " |", "|---|" + "---|" * len(ordre)]
    md = ["## Notation humaine à l'aveugle (notes moyennes, de 0 à 2)\n", *entete]
    md += [f"| {c} | " + " | ".join(fmt(score(v, c)) for v in ordre) + " |" for c in CRITERES]
    md.append("| **moyenne des 5 critères principaux** | " + " | ".join(
        fmt(moyenne([s for s in (score(v, c) for c in PRINCIPAUX) if s is not None])) for v in ordre) + " |")
    md += ["\n### Par groupe de personnages (moyenne des 5 critères principaux)\n",
           "| Groupe | " + " | ".join(ordre) + " |", "|---|" + "---|" * len(ordre)]
    for groupe in GROUPES.values():
        md.append(f"| {groupe} | " + " | ".join(
            fmt(moyenne([s for s in (score(v, c, groupe) for c in PRINCIPAUX) if s is not None])) for v in ordre) + " |")
    if accord[1]:
        md.append(f"\nAccord entre notateurs : {accord[0]}/{accord[1]} cases notées à l'identique ({accord[0] / accord[1]:.0%}).")
    if oublis:
        md.append("\n**Cases encore vides** : " + ", ".join(f"{k} : {n}" for k, n in oublis.items()))

    if len(ordre) == 2:  # repères pour l'analyse des réussites et des erreurs (rapport)
        par_requete = defaultdict(dict)
        for (code, c), n in moyennes.items():
            if c in PRINCIPAUX:
                par_requete[infos[code]["id"]].setdefault(infos[code]["version"], []).append(n)
        ecarts = sorted((moyenne(d[ordre[1]]) - moyenne(d[ordre[0]]), i) for i, d in par_requete.items()
                        if ordre[0] in d and ordre[1] in d)
        md += [f"\n### Plus grands écarts ({ordre[1]} − {ordre[0]}, moyenne des critères principaux)\n"]
        md += [f"- {i} : {e:+.2f}" for e, i in ecarts[-5:][::-1] if e > 0]
        md += [f"- {i} : {e:+.2f}" for e, i in ecarts[:5] if e < 0]
    return md + [""]


def metriques_auto(resultats):
    reponses = [x for r in resultats for x in r.get("reponses", []) + r.get("tours", [])]
    n = len(reponses)
    aveux = [x["aveu"] for x in reponses if "aveu" in x]
    return {"réponses analysées": n,
            "taux de fuite": sum(bool(x["fuites"]) for x in reponses) / n,
            "taux d'aveu correct (confrontations)": moyenne(aveux),
            "sortie du rôle": sum(x["hors_role"] for x in reponses) / n,
            "moins de 2 phrases": sum(x["phrases"] < 2 for x in reponses) / n,
            "plus de 5 phrases": sum(x["phrases"] > 5 for x in reponses) / n,
            "plus d'une didascalie": sum(x["didascalies"] > 1 for x in reponses) / n,
            "longueur moyenne (tokens)": moyenne([x["tokens"] for x in reponses if "tokens" in x])}


def tableau_auto(versions, tests):
    ordre = list(versions)
    auto = {v: metriques_auto(rs) for v, rs in versions.items()}
    md = ["## Métriques automatiques (tous les tirages, sans filtre de sortie)\n",
          "| Métrique | " + " | ".join(ordre) + " |", "|---|" + "---|" * len(ordre)]
    for nom in auto[ordre[0]]:
        if nom in ("réponses analysées", "longueur moyenne (tokens)"):
            ligne = [f"{auto[v][nom]:.0f}" if auto[v][nom] is not None else "–" for v in ordre]
        else:
            ligne = [fmt(auto[v][nom], pourcent=True) for v in ordre]
        md.append(f"| {nom} | " + " | ".join(ligne) + " |")
    md += ["\n### Taux de fuite par groupe de personnages\n",
           "| Groupe | " + " | ".join(ordre) + " |", "|---|" + "---|" * len(ordre)]
    for cle, groupe in GROUPES.items():
        cellules = []
        for v in ordre:
            rs = [r for r in versions[v] if tests[r["id"]]["vu"] == cle]
            cellules.append(fmt(metriques_auto(rs)["taux de fuite"], pourcent=True) if rs else "–")
        md.append(f"| {groupe} | " + " | ".join(cellules) + " |")
    md.append("\n### Mots interdits échappés (les plus fréquents)\n")
    for v in ordre:
        mots = Counter(m for r in versions[v] for x in r.get("reponses", []) + r.get("tours", []) for m in x["fuites"])
        md.append(f"- {v} : " + (", ".join(f"« {m} » ×{k}" for m, k in mots.most_common(8)) or "aucun"))
    return md + [""]


def tracer(moyennes, infos, ordre, chemin):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4), gridspec_kw={"width_ratios": [2.2, 1]})
    largeur = 0.8 / len(ordre)
    for i, v in enumerate(ordre):
        valeurs = [moyenne([n for (code, c), n in moyennes.items() if c == crit and infos[code]["version"] == v]) or 0
                   for crit in CRITERES]
        a.bar([x + i * largeur for x in range(len(CRITERES))], valeurs, largeur, label=v)
        groupes = [moyenne([n for (code, c), n in moyennes.items() if c in PRINCIPAUX
                            and infos[code]["version"] == v and infos[code]["groupe"] == g]) or 0
                   for g in GROUPES.values()]
        b.bar([x + i * largeur for x in range(len(GROUPES))], groupes, largeur, label=v)
    a.set_xticks([x + largeur * (len(ordre) - 1) / 2 for x in range(len(CRITERES))])
    a.set_xticklabels(CRITERES, rotation=20, ha="right")
    a.set_title("Par critère (toutes les requêtes)")
    b.set_xticks([x + largeur * (len(ordre) - 1) / 2 for x in range(len(GROUPES))])
    b.set_xticklabels([COURTS[g] for g in GROUPES.values()])
    b.set_title("Par groupe (5 critères principaux)")
    for ax in (a, b):
        ax.set_ylim(0, 2.45)  # place pour la légende au-dessus des barres
        ax.set_yticks([0, 0.5, 1, 1.5, 2])
        ax.set_ylabel("note moyenne (0 à 2)")
        ax.legend(ncol=len(ordre), loc="upper center")
    fig.tight_layout()
    fig.savefig(chemin, dpi=150)
    plt.close(fig)


def commande_auto(args):
    versions = charger_resultats(args.resultats)
    if not versions:
        sys.exit(f"Aucun fichier eval_<version>.jsonl dans {args.resultats}.")
    print("\n".join(tableau_auto(versions, {t["id"]: t for t in charger_tests()})))


def commande_agreger(args):
    dossier = Path(args.resultats)
    versions = charger_resultats(dossier)
    if not versions:
        sys.exit(f"Aucun fichier eval_<version>.jsonl dans {dossier}.")
    tests = {t["id"]: t for t in charger_tests()}
    feuilles = [Path(f) for f in args.feuilles] or [dossier / "notation_aveugle.csv"]
    cles_chemin = dossier / "notation_cles.json"
    md = [f"# Évaluation : {' vs '.join(versions)}\n"]
    if cles_chemin.exists() and all(f.exists() for f in feuilles):
        moyennes, infos, accord, oublis = notes_humaines(feuilles, json.loads(cles_chemin.read_text(encoding="utf-8")), tests)
        md += tableau_humain(moyennes, infos, accord, oublis, list(versions))
        tracer(moyennes, infos, list(versions), dossier / "scores_evaluation.png")
    else:
        md.append("*Pas de feuille de notation : seules les métriques automatiques sont calculées.*\n")
    md += tableau_auto(versions, tests)
    (dossier / "tableau_evaluation.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--resultats", default=str(RESULTATS), help="dossier des résultats (par défaut results/)")
    sous = parser.add_subparsers(dest="commande", required=True)
    sous.add_parser("verifier", help="contrôle du jeu de test")
    p = sous.add_parser("generer", help="réponses d'une version du modèle")
    p.add_argument("--version", required=True, help="nom de la version, par exemple baseline ou lora")
    p.add_argument("--adaptateur", help="dossier ou dépôt Hugging Face de l'adaptateur LoRA")
    p.add_argument("--modele", help="modèle de base (par défaut celui de src/config.py)")
    p.add_argument("--tirages", type=int, default=5, help="tirages par requête à un tour (le 1er est noté)")
    p.add_argument("--ids", help="sous-ensemble de requêtes, séparées par des virgules (test rapide)")
    sous.add_parser("auto", help="métriques automatiques seules")
    p = sous.add_parser("feuille", help="feuille de notation à l'aveugle")
    p.add_argument("--ecraser", action="store_true", help="refaire la feuille même si elle existe")
    p = sous.add_parser("agreger", help="tableau final, une fois les notes saisies")
    p.add_argument("feuilles", nargs="*", help="feuilles remplies (une par notateur)")
    args = parser.parse_args()
    if args.commande == "verifier":
        case, fiches = charger_affaire(AFFAIRE)
        tests = charger_tests()
        problemes = verifier_tests(tests, case, fiches)
        types = Counter(t["type"] for t in tests)
        print(f"{len(tests)} requêtes ; {dict(types)} ; jamais vu : {sum(t['vu'] == 'non' for t in tests)}")
        print("\n".join(problemes) if problemes else "jeu de test conforme au §11")
        sys.exit(1 if problemes else 0)
    {"generer": commande_generer, "auto": commande_auto, "feuille": commande_feuille,
     "agreger": commande_agreger}[args.commande](args)


if __name__ == "__main__":
    main()
