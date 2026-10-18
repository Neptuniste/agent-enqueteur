"""Vérifie une affaire avant de s'en servir (cahier des charges, §4.1, §4.2, §7 et §8.4).

    python cases/check_case.py                          # vérifie cases/main_case
    python cases/check_case.py cases/theatre_miroir     # vérifie une autre affaire
    python cases/check_case.py --autotest               # vérifie aussi que le vérificateur détecte des erreurs plantées

À relancer après chaque modification de case.json ou d'une fiche.
Code de sortie 1 s'il reste au moins une ERREUR ; les avertissements n'empêchent pas de continuer.
"""

import argparse
import copy
import json
import os
import re
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from src.config import MAX_CONTEXT, MAX_LENGTH, MAX_HISTORY_TURNS, MODEL_NAME  # noqa: E402
from src.game_state import (GameState, charger_affaire, secrets_ouverts_par,  # noqa: E402
                            texte_du_dossier)
from src.guard import REPLIQUE_DE_REPLI, detecter_fuites, generer_sans_fuite, normaliser  # noqa: E402
from src.prompt_builder import MODES, REGLES, build_system_prompt  # noqa: E402

DOSSIER_DEFAUT = ROOT / "cases" / "main_case"

SCHEMA_AFFAIRE = {"id": str, "titre": str, "source": str, "cadre": dict, "victime": dict,
                  "personnages": dict, "chronologie": list, "coupable": str, "mobile": str,
                  "moyen": str, "opportunite": str, "preuves": dict, "documents": list,
                  "pieces": list, "solution": str, "aveu_final": str}
SCHEMA_CADRE = {"lieu": str, "date": str, "contexte_public": str}
SCHEMA_VICTIME = {"id": str, "nom": str, "identite": str, "cause_deces": str, "heure_deces": str}
SCHEMA_CHRONO = {"quand": str, "fait": str}
SCHEMA_DOCUMENT = {"id": str, "titre": str, "fichier": str}
SCHEMA_PIECE = {"id": str, "nom": str, "description": str, "document": str,
                "disponible_au_depart": bool}
SCHEMA_FICHE = {"id": str, "nom": str, "role_enquete": str, "identite": str, "ton": str,
                "attitude": str, "verites": list, "alibi": str, "relations": dict,
                "secrets": list, "ignore": list}
SCHEMA_SECRET = {"id": str, "verite": str, "mensonge": str, "revele_si": list, "aveu": str,
                 "debloque": list, "mots_interdits": list}
VIDES_PERMIS = {"verite", "aveu"}  # seulement pour le meurtre du coupable (barrière 3)

ROLES = {"coupable", "fausse_piste", "temoin"}
PREUVES = {"coupable", "mobile", "moyen", "opportunite"}
NB_PERSONNAGES = (6, 8)       # §2, §6.1
NB_PIECES = (8, 12)           # §2, §6.1
TOKENS_FICHE = (300, 500)     # §7.2
TOKENS_DEBUT_MAX = 1000       # §8.4 : message système en début d'interrogatoire
TOKENS_SYSTEME_MAX = 1500     # §8.4 : message système au pire (fin de partie)
TOKENS_ECHANGE = 150          # §8.4 : ~30 (question) + ~120 (réponse)
TOURS_ENTRAINEMENT = 4        # §9.6 : 1 à 4 tours par exemple
BUDGET_REPONSE = 150          # §8.2 : max_new_tokens
ID_VALIDE = re.compile(r"^[a-z][a-z0-9_]*$")
HEURE = re.compile(r"\b\d{1,2}h\d{2}\b")


class Rapport:
    """Messages classés par section : ERREUR, ATTENTION ou info."""

    def __init__(self):
        self.messages = []
        self.sections = []
        self._section = "Général"

    def section(self, nom):
        self._section = nom
        if nom not in self.sections:
            self.sections.append(nom)

    def erreur(self, msg):
        self.messages.append((self._section, "ERREUR", msg))

    def attention(self, msg):
        self.messages.append((self._section, "ATTENTION", msg))

    def info(self, msg):
        self.messages.append((self._section, "info", msg))

    @property
    def erreurs(self):
        return [m for _, niveau, m in self.messages if niveau == "ERREUR"]

    @property
    def attentions(self):
        return [m for _, niveau, m in self.messages if niveau == "ATTENTION"]

    def afficher(self):
        for section in self.sections:
            print(f"\n== {section} ==")
            lignes = [(n, m) for s, n, m in self.messages if s == section]
            if not any(n != "info" for n, _ in lignes):
                print("  OK")
            for niveau, msg in lignes:
                prefixe = "  " if niveau == "info" else f"  {niveau} : "
                print(prefixe + msg)


# --- Outils -------------------------------------------------------------------------------

def fragments(texte, longueur_min=30):
    """Découpe un texte en phrases assez longues pour qu'une présence ne soit pas un hasard."""
    morceaux = re.split(r"(?<=[.!?;:])\s+", texte)
    return [m for m in morceaux if len(m) >= longueur_min]


def textes_de(obj):
    """Toutes les chaînes d'un objet JSON, récursivement."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for valeur in obj.values():
            yield from textes_de(valeur)
    elif isinstance(obj, list):
        for valeur in obj:
            yield from textes_de(valeur)


def charger_compteur():
    """Compteur de tokens : vrai tokenizer si possible, sinon estimation."""
    try:
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained(MODEL_NAME)
        return (lambda t: len(tok.encode(t, add_special_tokens=False))), f"tokenizer de {MODEL_NAME}"
    except Exception:
        pass
    try:
        from tokenizers import Tokenizer
        tok = Tokenizer.from_pretrained(MODEL_NAME)
        return (lambda t: len(tok.encode(t, add_special_tokens=False).ids)), f"tokenizer de {MODEL_NAME}"
    except Exception:
        pass
    return estimer_tokens, "ESTIMATION (2,9 caractères par token) : installer transformers pour un compte exact"


def estimer_tokens(texte):
    return round(len(texte) / 2.9)


def etats_a_tester(case, fiche):
    """Début, chaque pièce présentée, fin de partie, et chaque pièce présentée en fin de partie."""
    toutes = [p["id"] for p in case["pieces"]]
    avouables = [s["id"] for s in fiche["secrets"] if s["revele_si"]]
    fin = {"secrets_avoues": avouables, "pieces_montrees": toutes}
    etats = [("début", {})]
    etats += [(f"{p} présentée", {"piece_presentee": p}) for p in toutes]
    etats.append(("fin de partie", fin))
    etats += [(f"fin de partie, {p} présentée", dict(fin, piece_presentee=p)) for p in toutes]
    return etats


# --- 1. Structure -------------------------------------------------------------------------

def _schema(obj, schema, ou, r, vides_permis=()):
    if not isinstance(obj, dict):
        r.erreur(f"{ou} : un objet JSON est attendu")
        return
    for cle, typ in schema.items():
        if cle not in obj:
            r.erreur(f"{ou} : champ manquant « {cle} »")
            continue
        valeur = obj[cle]
        if not isinstance(valeur, typ):
            r.erreur(f"{ou}.{cle} : type {typ.__name__} attendu")
        elif typ is str and not valeur.strip() and cle not in vides_permis:
            r.erreur(f"{ou}.{cle} : texte vide")
        elif typ is list and cle != "chronologie":
            for i, elem in enumerate(valeur):
                if isinstance(elem, str) and not elem.strip():
                    r.erreur(f"{ou}.{cle}[{i}] : texte vide")
        elif typ is dict:
            for sous_cle, sous_val in valeur.items():
                if isinstance(sous_val, str) and not sous_val.strip():
                    r.erreur(f"{ou}.{cle}.{sous_cle} : texte vide")
    for cle in obj:
        if cle not in schema:
            r.attention(f"{ou} : champ inconnu « {cle} » (à documenter au §7 du cahier des charges)")


def verifier_structure(case, fiches, r):
    r.section("1. Structure (format §7)")
    _schema(case, SCHEMA_AFFAIRE, "case.json", r)
    if r.erreurs:
        return
    _schema(case["cadre"], SCHEMA_CADRE, "case.json:cadre", r)
    _schema(case["victime"], SCHEMA_VICTIME, "case.json:victime", r)
    for i, entree in enumerate(case["chronologie"]):
        _schema(entree, SCHEMA_CHRONO, f"case.json:chronologie[{i}]", r)
    for i, doc in enumerate(case["documents"]):
        _schema(doc, SCHEMA_DOCUMENT, f"case.json:documents[{i}]", r)
    for i, piece in enumerate(case["pieces"]):
        _schema(piece, SCHEMA_PIECE, f"case.json:pieces[{i}]", r)
    for perso_id, fiche in fiches.items():
        _schema(fiche, SCHEMA_FICHE, perso_id, r)
        for i, secret in enumerate(fiche.get("secrets", []) if isinstance(fiche, dict) else []):
            _schema(secret, SCHEMA_SECRET, f"{perso_id}:secrets[{i}]", r, VIDES_PERMIS)
    for liste in ("verites", "ignore"):
        for perso_id, fiche in fiches.items():
            if not all(isinstance(x, str) for x in fiche.get(liste, [])):
                r.erreur(f"{perso_id}.{liste} : liste de textes attendue")


# --- 2. Références et fichiers ------------------------------------------------------------

def verifier_references(case, fiches, dossier, chemins, r):
    r.section("2. Références et fichiers")
    pieces = [p["id"] for p in case["pieces"]]
    victime = case["victime"]["id"]
    tous_ids = pieces + [d["id"] for d in case["documents"]] + list(fiches) + [victime]
    for ident in tous_ids:
        if not ID_VALIDE.match(ident):
            r.erreur(f"identifiant mal formé (minuscules, chiffres, _) : {ident}")
    for nom, ids in (("pièce", pieces), ("document", [d["id"] for d in case["documents"]])):
        doublons = {i for i in ids if ids.count(i) > 1}
        if doublons:
            r.erreur(f"{nom}s en double : {sorted(doublons)}")

    if set(case["personnages"]) != set(fiches):
        r.erreur(f"case.json:personnages {sorted(case['personnages'])} ne correspond pas aux fiches "
                 f"{sorted(fiches)}")
    for perso_id, fiche in fiches.items():
        if case["personnages"].get(perso_id) not in (None, fiche["nom"]):
            r.erreur(f"{perso_id} : nom différent dans case.json et dans la fiche")
        if fiche["id"] != perso_id:
            r.erreur(f"{perso_id} : id de fiche incohérent")
    if case["coupable"] not in fiches:
        r.erreur(f"case.json:coupable inconnu : {case['coupable']}")

    for perso_id, fiche in fiches.items():
        for cle in fiche["relations"]:
            if cle == perso_id:
                r.erreur(f"{perso_id} : relation avec lui-même")
            elif cle not in fiches and cle != victime:
                r.erreur(f"{perso_id} : relation avec un personnage inconnu « {cle} »")
        for secret in fiche["secrets"]:
            for champ in ("revele_si", "debloque"):
                for p in secret[champ]:
                    if p not in pieces:
                        r.erreur(f"{perso_id}/{secret['id']}.{champ} : pièce inconnue « {p} »")

    if set(case["preuves"]) != PREUVES:
        r.erreur(f"case.json:preuves doit contenir exactement {sorted(PREUVES)}")
    for cle, liste in case["preuves"].items():
        if not isinstance(liste, list) or not liste:
            r.erreur(f"case.json:preuves.{cle} : au moins une pièce attendue (§2, solution déductible)")
            continue
        for p in liste:
            if p not in pieces:
                r.erreur(f"case.json:preuves.{cle} : pièce inconnue « {p} »")

    for chemin, fiche in chemins.items():
        if chemin.stem != fiche.get("id"):
            r.erreur(f"{chemin.name} : le nom du fichier doit être l'id de la fiche ({fiche.get('id')})")
    references = set()
    for doc in case["documents"]:
        references.add(doc["fichier"])
    for piece in case["pieces"]:
        references.add(piece["document"])
    for fichier in sorted(references):
        if not (dossier / fichier).is_file():
            r.erreur(f"fichier introuvable : {fichier}")
    assets = dossier / "assets"
    if assets.is_dir():
        for chemin in sorted(assets.rglob("*")):
            relatif = chemin.relative_to(dossier).as_posix()
            if chemin.is_file() and chemin.name != ".gitkeep" and relatif not in references:
                r.attention(f"fichier non référencé dans case.json : {relatif}")


# --- 3. Contenu (règles du cahier des charges) -------------------------------------------

def verifier_contenu(case, fiches, r):
    r.section("3. Contenu (§2, §4.1, §7.2)")
    if not NB_PERSONNAGES[0] <= len(fiches) <= NB_PERSONNAGES[1]:
        r.erreur(f"{len(fiches)} personnages, {NB_PERSONNAGES[0]} à {NB_PERSONNAGES[1]} attendus")
    if not NB_PIECES[0] <= len(case["pieces"]) <= NB_PIECES[1]:
        r.erreur(f"{len(case['pieces'])} pièces, {NB_PIECES[0]} à {NB_PIECES[1]} attendues")

    roles = {pid: f["role_enquete"] for pid, f in fiches.items()}
    for pid, role in roles.items():
        if role not in ROLES:
            r.erreur(f"{pid} : role_enquete « {role} » inconnu ({', '.join(sorted(ROLES))})")
    coupables = [pid for pid, role in roles.items() if role == "coupable"]
    if coupables != [case["coupable"]]:
        r.erreur(f"il faut exactement un coupable, celui de case.json ({case['coupable']}) ; "
                 f"fiches marquées coupable : {coupables}")
    for role in ("fausse_piste", "temoin"):
        if role not in roles.values():
            r.attention(f"aucun personnage « {role} »")

    depart = {p["id"] for p in case["pieces"] if p["disponible_au_depart"]}
    if len(depart) < 3:
        r.attention(f"seulement {len(depart)} pièce(s) au départ : le joueur risque d'être bloqué")
    debloquees = set()

    for pid, fiche in fiches.items():
        ids = [s["id"] for s in fiche["secrets"]]
        if len(ids) != len(set(ids)):
            r.erreur(f"{pid} : identifiants de secrets en double")
        for liste in ("verites", "ignore"):
            if not fiche[liste]:
                r.attention(f"{pid}.{liste} est vide")
            if len(fiche[liste]) != len(set(fiche[liste])):
                r.attention(f"{pid}.{liste} contient des doublons")
        if not fiche["relations"]:
            r.attention(f"{pid} : aucune relation")
        if not fiche["secrets"]:
            r.erreur(f"{pid} : aucun secret (chaque personnage doit cacher quelque chose)")

        jamais = [s for s in fiche["secrets"] if not s["revele_si"]]
        for secret in fiche["secrets"]:
            ou = f"{pid}/{secret['id']}"
            if not secret["mensonge"].strip():
                r.erreur(f"{ou} : mensonge vide (version à donner tant que le secret est verrouillé)")
            if secret["revele_si"]:
                if not secret["verite"].strip() or not secret["aveu"].strip():
                    r.erreur(f"{ou} : un secret révélable doit avoir une vérité et une consigne d'aveu")
            elif pid != case["coupable"]:
                r.erreur(f"{ou} : secret jamais révélable (revele_si vide) chez un innocent")
            for liste in ("revele_si", "debloque", "mots_interdits"):
                if len(secret[liste]) != len(set(secret[liste])):
                    r.attention(f"{ou}.{liste} contient des doublons")
            if set(secret["revele_si"]) & set(secret["debloque"]):
                r.erreur(f"{ou} : une pièce ne peut pas à la fois ouvrir et être débloquée par ce secret")
            for mot in secret["mots_interdits"]:
                if len(normaliser(mot)) < 4:
                    r.attention(f"{ou} : mot interdit trop court, risque de fausses alertes : « {mot} »")
            debloquees.update(secret["debloque"])

        if pid == case["coupable"]:
            # Barrière 3 : le meurtre est un secret jamais révélé, sans vérité ni aveu.
            if len(jamais) != 1:
                r.erreur(f"{pid} (barrière 3) : le coupable doit avoir exactement un secret sans "
                         f"revele_si (le meurtre), trouvé {len(jamais)}")
            for secret in jamais:
                if secret["verite"] or secret["aveu"] or secret["debloque"]:
                    r.erreur(f"{pid}/{secret['id']} (barrière 3) : le meurtre ne doit avoir ni vérité, "
                             "ni aveu, ni déblocage : sa vérité ne doit jamais entrer dans le prompt")
                if not secret["mots_interdits"]:
                    r.erreur(f"{pid}/{secret['id']} : mots interdits vides pour le meurtre")

    for p in sorted(depart & debloquees):
        r.attention(f"{p} est disponible au départ ET débloquée par un aveu")

    for texte in textes_de([case, list(fiches.values())]):
        if re.search(r"TODO|XXX|\?\?\?", texte):
            r.attention(f"texte provisoire : « {texte[:60]}… »")
        if "  " in texte or texte != texte.strip():
            r.attention(f"espaces en trop : « {texte[:60]}… »")


# --- 4. Chaîne d'indices (§4.2) -----------------------------------------------------------

def simuler(case, fiches):
    """Parcours en largeur : chaque pièce disponible est montrée à chaque personnage."""
    etat = GameState.nouvelle_partie(case, fiches)
    profondeur = {p: 0 for p in etat.disponibles}
    origine, revele_par = {}, {}
    file = deque(etat.disponibles)
    while file:
        piece = file.popleft()
        for perso_id in fiches:
            avant = set(etat.avoues.get(perso_id, []))
            _, nouvelles = etat.presenter(perso_id, piece)
            nouveaux = [s for s in etat.avoues.get(perso_id, []) if s not in avant]
            for s in nouveaux:
                revele_par[(perso_id, s)] = piece
            for n in nouvelles:
                profondeur[n] = profondeur[piece] + 1
                origine[n] = (perso_id, nouveaux, piece)
                file.append(n)
    return etat, profondeur, origine, revele_par


def verifier_chaine(case, fiches, r):
    r.section("4. Chaîne d'indices (§4.2) : la partie est-elle jouable ?")
    _, profondeur, origine, revele_par = simuler(case, fiches)
    for piece in case["pieces"]:
        if piece["id"] not in profondeur:
            r.erreur(f"pièce inatteignable : {piece['id']} (aucun aveu accessible ne la débloque)")
    for pid, fiche in fiches.items():
        for secret in fiche["secrets"]:
            if secret["revele_si"] and (pid, secret["id"]) not in revele_par:
                r.erreur(f"secret jamais avouable : {pid}/{secret['id']} (pièces {secret['revele_si']} "
                         "inatteignables)")
            if not secret["revele_si"] and (pid, secret["id"]) in revele_par:
                r.erreur(f"{pid}/{secret['id']} : le meurtre a été avoué pendant la simulation")
    for cle, liste in case["preuves"].items():
        for p in liste:
            if p not in profondeur:
                r.erreur(f"preuve inatteignable ({cle}) : {p}")
        atteintes = [p for p in liste if p in profondeur]
        if atteintes:
            r.info(f"preuve du {cle} : {', '.join(atteintes)} (profondeur max "
                   f"{max(profondeur[p] for p in atteintes)} aveu(x))")
    for p in sorted(origine, key=lambda x: (profondeur[x], x)):
        perso_id, secrets, declencheur = origine[p]
        r.info(f"{p} (profondeur {profondeur[p]}) ← aveu de {perso_id} "
               f"[{', '.join(secrets)}] face à {declencheur}")
    r.info(f"{len(revele_par)} secrets avouables sur "
           f"{sum(len(f['secrets']) for f in fiches.values())} (le meurtre ne l'est jamais)")


# --- 5. Barrières anti-fuite dans les prompts (§4.1) --------------------------------------

def verifier_barrieres(case, fiches, dossier, r):
    r.section("5. Barrières anti-fuite (§4.1) : prompts rendus dans tous les états")
    pieces = {p["id"]: p for p in case["pieces"]}
    interdits_solution = []
    for cle in ("solution", "aveu_final", "mobile", "moyen", "opportunite"):
        interdits_solution += fragments(case[cle])
    nb_prompts = 0
    for pid, fiche in fiches.items():
        for nom_etat, etat in etats_a_tester(case, fiche):
            prompt = normaliser(build_system_prompt(fiche, case, etat, mode="verrouille"))
            nb_prompts += 1
            avoues = set(etat.get("secrets_avoues", []))
            piece_id = etat.get("piece_presentee")
            montrees = list(etat.get("pieces_montrees", [])) + ([piece_id] if piece_id else [])
            autorise = normaliser(" ".join(pieces[p]["description"] for p in montrees))
            ouverts = secrets_ouverts_par(fiche, piece_id) if piece_id else []
            reveles = avoues | {s["id"] for s in ouverts}
            ou = f"{pid} ({nom_etat})"
            for secret in fiche["secrets"]:
                if secret["id"] in reveles:
                    if normaliser(secret["mensonge"]) in prompt:
                        r.erreur(f"{ou} : le mensonge du secret avoué « {secret['id']} » est encore donné")
                    continue
                if normaliser(secret["mensonge"]) not in prompt:
                    r.erreur(f"{ou} : mensonge du secret verrouillé « {secret['id']} » absent du prompt")
                for frag in fragments(secret["verite"]):
                    if normaliser(frag) in prompt and normaliser(frag) not in autorise:
                        r.erreur(f"{ou} : vérité verrouillée dans le prompt (barrière 2) : « {frag[:50]}… »")
                for mot in secret["mots_interdits"]:
                    if normaliser(mot) in prompt and normaliser(mot) not in autorise:
                        r.erreur(f"{ou} : mot interdit « {mot} » de « {secret['id']} » déjà dans le prompt")
            if pid == case["coupable"] and "coupable" in prompt:
                r.erreur(f"{ou} : le mot « coupable » apparaît dans le prompt du coupable (barrière 3)")
            for frag in interdits_solution:
                if normaliser(frag) in prompt:
                    r.erreur(f"{ou} : un passage de la solution est dans le prompt : « {frag[:50]}… »")
    r.info(f"{nb_prompts} prompts verrouillés rendus et contrôlés")

    # Barrière 4 : un mot déjà public ne peut pas servir au filtre.
    depart = [p["id"] for p in case["pieces"] if p["disponible_au_depart"]]
    public = normaliser(texte_du_dossier(case, dossier, depart))
    for pid, fiche in fiches.items():
        for secret in fiche["secrets"]:
            for mot in secret["mots_interdits"]:
                if normaliser(mot) in public:
                    r.attention(f"{pid}/{secret['id']} : « {mot} » est déjà dans le dossier de départ, "
                                "le filtre ne pourra pas s'en servir")
            if secret["revele_si"] and not secret["mots_interdits"] and not set(secret["revele_si"]) & set(depart):
                r.attention(f"{pid}/{secret['id']} : secret débloqué en cours de partie sans mot interdit")

    # Mode complet (prompt A) : il doit bien contenir les vérités, sinon la comparaison A/B ne vaut rien.
    for pid, fiche in fiches.items():
        prompt = normaliser(build_system_prompt(fiche, case, {}, mode="complet"))
        for secret in fiche["secrets"]:
            if secret["verite"] and normaliser(secret["verite"]) not in prompt:
                r.erreur(f"{pid} (mode complet) : la vérité de « {secret['id']} » manque au prompt A")


# --- 6. Longueurs (§7.2, §8.4) ------------------------------------------------------------

def verifier_longueurs(case, fiches, compter, nom_compteur, r):
    r.section("6. Longueurs en tokens (§7.2, §8.4)")
    r.info(f"comptage : {nom_compteur}")
    entete = compter(REGLES + "\n\n## L'affaire\n" + case["cadre"]["contexte_public"] + "\n\n")
    r.info(f"règles + contexte de l'affaire : {entete} tokens (communs à tous)")
    maxi_global = 0
    for pid, fiche in fiches.items():
        debut = compter(build_system_prompt(fiche, case, {}))
        fiche_seule = debut - entete
        maxi = max(compter(build_system_prompt(fiche, case, etat, mode))
                   for _, etat in etats_a_tester(case, fiche) for mode in MODES)
        maxi_global = max(maxi_global, maxi)
        r.info(f"{pid:20} fiche {fiche_seule:4} | prompt au début {debut:4} | au pire {maxi:4}")
        if not TOKENS_FICHE[0] <= fiche_seule <= TOKENS_FICHE[1]:
            r.attention(f"{pid} : fiche de {fiche_seule} tokens, {TOKENS_FICHE[0]} à {TOKENS_FICHE[1]} visés")
        if debut > TOKENS_DEBUT_MAX:
            r.attention(f"{pid} : message système de {debut} tokens au début, {TOKENS_DEBUT_MAX} au plus visés")
        if maxi > TOKENS_SYSTEME_MAX:
            r.attention(f"{pid} : message système jusqu'à {maxi} tokens, {TOKENS_SYSTEME_MAX} au plus visés")
    historique = MAX_HISTORY_TURNS * TOKENS_ECHANGE
    inference = maxi_global + historique + BUDGET_REPONSE
    message = (f"inférence au pire : {maxi_global} (système) + {historique} ({MAX_HISTORY_TURNS} échanges) "
               f"+ {BUDGET_REPONSE} (réponse) = {inference} / MAX_CONTEXT {MAX_CONTEXT}")
    (r.erreur if inference > MAX_CONTEXT else r.info)(message)
    entrainement = maxi_global + TOURS_ENTRAINEMENT * TOKENS_ECHANGE
    message = (f"entraînement au pire : {maxi_global} (système) + {TOURS_ENTRAINEMENT} tours "
               f"= {entrainement} / MAX_LENGTH {MAX_LENGTH}")
    (r.attention if entrainement > MAX_LENGTH else r.info)(message)


# --- 7. Filtre de sortie (barrière 4) -----------------------------------------------------

def verifier_filtre(case, fiches, r):
    r.section("7. Filtre de sortie (barrière 4) : autotest")
    nb = 0
    for pid, fiche in fiches.items():
        for secret in fiche["secrets"]:
            autres = {normaliser(m) for s in fiche["secrets"] if s is not secret for m in s["mots_interdits"]}
            for mot in secret["mots_interdits"]:
                reponse = f"*(Un temps.)* Eh bien... {mot.upper()}, voilà tout."
                nb += 1
                if mot not in detecter_fuites(reponse, fiche, []):
                    r.erreur(f"{pid}/{secret['id']} : le filtre ne détecte pas « {mot} »")
                if normaliser(mot) not in autres and detecter_fuites(reponse, fiche, [secret["id"]]):
                    r.erreur(f"{pid}/{secret['id']} : « {mot} » encore filtré après l'aveu")
                if detecter_fuites(reponse, fiche, [], deja_connu=f"question : {mot} ?"):
                    r.erreur(f"{pid}/{secret['id']} : « {mot} » filtré alors que le joueur l'a dit")
        if detecter_fuites(REPLIQUE_DE_REPLI, fiche, []):
            r.erreur(f"{pid} : la réplique de repli contient un mot interdit")
    rose = fiches[case["coupable"]]
    mot = next(m for s in rose["secrets"] for m in s["mots_interdits"])
    reponses = iter([f"Bon... {mot}.", "Je n'ai rien à ajouter."])
    reponse, evitees = generer_sans_fuite(lambda: next(reponses), rose, [], "")
    if reponse != "Je n'ai rien à ajouter." or evitees != 1:
        r.erreur("generer_sans_fuite ne régénère pas après une fuite")
    reponse, _ = generer_sans_fuite(lambda: f"{mot} !", rose, [], "")
    if reponse != REPLIQUE_DE_REPLI:
        r.erreur("generer_sans_fuite ne renvoie pas la réplique de repli après 3 fuites")
    r.info(f"{nb} mots interdits testés (détection, levée après aveu, exception si le joueur l'a dit)")


# --- 8. Cohérence des heures --------------------------------------------------------------

def verifier_heures(case, fiches, dossier, r):
    r.section("8. Cohérence des heures avec la chronologie")
    connues = set()
    for entree in case["chronologie"]:
        connues.update(HEURE.findall(entree["quand"] + " " + entree["fait"]))
    sources = [(pid, texte) for pid, fiche in fiches.items() for texte in textes_de(fiche)]
    sources += [(p["id"], p["description"]) for p in case["pieces"]]
    sources += [("case.json", case["cadre"]["contexte_public"])]
    for doc in case["documents"]:
        sources.append((doc["fichier"], (dossier / doc["fichier"]).read_text(encoding="utf-8")))
    for piece in case["pieces"]:
        sources.append((piece["document"], (dossier / piece["document"]).read_text(encoding="utf-8")))
    vues = set()
    for ou, texte in sources:
        for heure in HEURE.findall(texte):
            vues.add(heure)
            if heure not in connues:
                r.attention(f"{ou} : {heure} n'apparaît pas dans la chronologie de case.json")
    r.info(f"{len(vues)} heures citées, toutes rapprochées de la chronologie ({len(connues)} heures)")


# --- Ensemble -----------------------------------------------------------------------------

def verifier_tout(case, fiches, dossier, chemins, compter, nom_compteur):
    r = Rapport()
    verifier_structure(case, fiches, r)
    if r.erreurs:
        return r  # inutile d'aller plus loin sur un format cassé
    verifier_references(case, fiches, dossier, chemins, r)
    if r.erreurs:
        return r
    verifier_contenu(case, fiches, r)
    verifier_chaine(case, fiches, r)
    verifier_barrieres(case, fiches, dossier, r)
    verifier_longueurs(case, fiches, compter, nom_compteur, r)
    verifier_filtre(case, fiches, r)
    verifier_heures(case, fiches, dossier, r)
    return r


# Les erreurs plantées visent des éléments choisis dans l'affaire elle-même : l'autotest marche
# pour n'importe quelle affaire, pas seulement pour cases/main_case.

def _meurtre(c, f):
    return next(s for s in f[c["coupable"]]["secrets"] if not s["revele_si"])


def _avouable(fiche):
    return next(s for s in fiche["secrets"] if s["revele_si"])


def _innocent(c, f):
    return f[next(pid for pid in f if pid != c["coupable"])]


def _piece_debloquee(c, preuve):
    """Une pièce absente du dossier de départ : une preuve du coupable, ou au contraire une pièce
    qui n'est la preuve de rien."""
    preuves = {p for liste in c["preuves"].values() for p in liste}
    candidates = [p["id"] for p in c["pieces"] if not p["disponible_au_depart"]]
    choix = ([p for p in candidates if p in c["preuves"]["coupable"]] if preuve
             else [p for p in candidates if p not in preuves])
    return (choix or candidates)[0]


def _rendre_inatteignable(f, piece_id):
    for fiche in f.values():
        for secret in fiche["secrets"]:
            secret["debloque"] = [p for p in secret["debloque"] if p != piece_id]


def _mot_du_prompt(fiche):
    """Le mot le plus long de l'attitude, qui figure donc dans le prompt du personnage."""
    return max(re.findall(r"[^\W\d_]{6,}", fiche["attitude"]), key=len)


MUTATIONS = [
    ("pièce rendue inatteignable", "inatteignable",
     lambda c, f: _rendre_inatteignable(f, _piece_debloquee(c, preuve=False))),
    ("vérité recopiée dans les vérités libres", "barrière 2",
     lambda c, f: f[c["coupable"]]["verites"].append(_avouable(f[c["coupable"]])["verite"])),
    ("mot interdit déjà présent dans la fiche", "mot interdit",
     lambda c, f: _avouable(_innocent(c, f))["mots_interdits"].append(_mot_du_prompt(_innocent(c, f)))),
    ("vérité donnée au meurtre", "barrière 3",
     lambda c, f: _meurtre(c, f).update(verite="Tu as tué la victime.")),
    ("référence à une pièce inexistante", "pièce inconnue",
     lambda c, f: _avouable(_innocent(c, f)).update(revele_si=["piece_fantome"])),
    ("deux coupables", "exactement un coupable",
     lambda c, f: _innocent(c, f).update(role_enquete="coupable")),
    ("relation vers un inconnu", "personnage inconnu",
     lambda c, f: _innocent(c, f)["relations"].update(fantome="Un inconnu.")),
    ("preuve finale rendue inatteignable", "preuve inatteignable",
     lambda c, f: _rendre_inatteignable(f, _piece_debloquee(c, preuve=True))),
    ("mensonge effacé", "mensonge",
     lambda c, f: _avouable(f[c["coupable"]]).update(mensonge="")),
    ("meurtre sans mots interdits", "mots interdits vides",
     lambda c, f: _meurtre(c, f).update(mots_interdits=[])),
    ("fiche beaucoup trop longue", "inférence au pire",
     lambda c, f: _innocent(c, f)["verites"].append("Une phrase trop longue. " * 300)),
    ("champ manquant", "champ manquant",
     lambda c, f: _innocent(c, f).pop("attitude")),
]


def autotest(case, fiches, dossier, chemins):
    """Plante une erreur à la fois et vérifie que le vérificateur la signale."""
    print("\n== Autotest du vérificateur : chaque erreur plantée doit être détectée ==")
    echecs = 0
    for nom, attendu, muter in MUTATIONS:
        c, f = copy.deepcopy(case), copy.deepcopy(fiches)
        muter(c, f)
        r = verifier_tout(c, f, dossier, chemins, estimer_tokens, "estimation")
        trouve = any(attendu in e for e in r.erreurs)
        echecs += not trouve
        print(f"  {'détectée' if trouve else 'MANQUÉE '} : {nom}"
              + ("" if trouve else f" (erreurs : {r.erreurs[:2]})"))
    return echecs


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dossier", nargs="?", default=str(DOSSIER_DEFAUT))
    parser.add_argument("--autotest", action="store_true")
    args = parser.parse_args()
    dossier = Path(args.dossier)

    case, fiches = charger_affaire(dossier)
    chemins = {p: json.loads(p.read_text(encoding="utf-8"))
               for p in sorted((dossier / "characters").glob("*.json"))}
    compter, nom_compteur = charger_compteur()
    print(f"Vérification de {dossier.relative_to(ROOT) if dossier.is_relative_to(ROOT) else dossier} "
          f": « {case.get('titre', '?')} »")
    r = verifier_tout(case, fiches, dossier, chemins, compter, nom_compteur)
    r.afficher()
    echecs = autotest(case, fiches, dossier, chemins) if args.autotest else 0
    print(f"\nBilan : {len(r.erreurs)} erreur(s), {len(r.attentions)} avertissement(s)"
          + (f", {echecs} erreur(s) plantée(s) non détectée(s)" if args.autotest else ""))
    sys.exit(1 if r.erreurs or echecs else 0)


if __name__ == "__main__":
    main()
