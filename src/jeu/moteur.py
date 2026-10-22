"""Moteur de l'interface ludique : sessions de jeu, tours, aveux, carnet, accusation et score.

Il ne dépend pas de Gradio : chaque méthode publique prend des valeurs simples et renvoie un dictionnaire
sérialisable en JSON, ce qui la rend appelable depuis le navigateur et facile à tester. La logique d'un
tour (message système, filtre de sortie, état rétabli si la génération échoue) est celle de src/app.py.
"""

import secrets
import threading
import time

from src.app import Partie
from src.game_state import charger_affaire
from src.jeu.catalogue import carte_affaire, dossier_public, piece_publique, trouver_affaires

QUESTION_MAX = 500          # caractères
SESSIONS_MAX = 200          # au-delà, les parties les plus anciennes sont oubliées
GRADES = [(90, "Commissaire divisionnaire"), (75, "Inspecteur principal"), (50, "Inspecteur"),
          (0, "Inspecteur stagiaire")]
CATEGORIES = ("mobile", "moyen", "opportunite")


class ErreurDeJeu(ValueError):
    """Action impossible (session inconnue, pièce absente du dossier…) : message à montrer au joueur."""


class Session:
    def __init__(self, affaire_id, partie):
        self.affaire_id = affaire_id
        self.partie = partie
        self.questions = 0
        self.carnet = []
        self.recits = []    # pièces obtenues, racontées dans l'interrogatoire : {"perso", "apres", "texte"}
        self.verdict = None
        self.vue = time.time()


class MoteurDeJeu:
    def __init__(self, generer, affaires=None, mode="modele", modele_affiche=""):
        self.generer = generer
        self.affaires = affaires or trouver_affaires()
        self.mode, self.modele_affiche = mode, modele_affiche
        self._affaires_chargees = {}
        self.sessions = {}
        self._verrou_sessions = threading.Lock()
        self._verrou_modele = threading.Lock()    # un seul modèle en mémoire : une génération à la fois

    # --- affaires --------------------------------------------------------------------------------
    def affaire(self, affaire_id):
        if affaire_id not in self.affaires:
            raise ErreurDeJeu(f"affaire inconnue : {affaire_id}")
        if affaire_id not in self._affaires_chargees:
            case, fiches = charger_affaire(self.affaires[affaire_id])
            self._affaires_chargees[affaire_id] = (case, fiches)
        return self._affaires_chargees[affaire_id]

    def catalogue(self):
        cartes = [carte_affaire(*self.affaire(a)) for a in self.affaires]
        return {"affaires": cartes, "mode": self.mode, "modele": self.modele_affiche}

    # --- sessions --------------------------------------------------------------------------------
    def _session(self, ident):
        with self._verrou_sessions:
            session = self.sessions.get(ident)
        if session is None:
            raise ErreurDeJeu("partie introuvable : recommencez depuis le menu")
        session.vue = time.time()
        return session

    def ouvrir(self, affaire_id):
        case, fiches = self.affaire(affaire_id)
        ident = secrets.token_hex(8)
        with self._verrou_sessions:
            if len(self.sessions) >= SESSIONS_MAX:
                plus_ancienne = min(self.sessions, key=lambda k: self.sessions[k].vue)
                del self.sessions[plus_ancienne]
            self.sessions[ident] = Session(affaire_id, Partie(case, fiches, self.affaires[affaire_id]))
        return {"session": ident, **self.reprendre(ident)}

    def reprendre(self, ident):
        """Tout l'état d'une partie, pour l'afficher ou la reprendre après un rechargement de la page."""
        s = self._session(ident)
        case, fiches = self.affaire(s.affaire_id)
        historiques = {p: list(h) for p, h in s.partie.historiques.items() if h}
        return {"affaire": dossier_public(case, fiches, self.affaires[s.affaire_id]),
                "pieces": self._pieces(s), "historiques": historiques, "carnet": list(s.carnet),
                "recits": list(s.recits), "progression": self._progression(s), "verdict": s.verdict}

    # --- jeu -------------------------------------------------------------------------------------
    def _pieces(self, s):
        case, _ = self.affaire(s.affaire_id)
        pieces = {p["id"]: p for p in case["pieces"]}
        return [piece_publique(pieces[p], self.affaires[s.affaire_id]) for p in s.partie.jeu.disponibles]

    def _progression(self, s):
        case, fiches = self.affaire(s.affaire_id)
        jeu = s.partie.jeu
        return {"pieces": len(jeu.disponibles), "pieces_total": len(case["pieces"]),
                "aveux": sum(len(v) for v in jeu.avoues.values()),
                "aveux_total": sum(1 for f in fiches.values() for x in f["secrets"] if x["revele_si"]),
                "aveux_par_personnage": {p: len(v) for p, v in jeu.avoues.items()},
                "questions": s.questions}

    def interroger(self, ident, perso, question, piece=None):
        """Une question, éventuellement avec une pièce présentée. Renvoie la réplique et ce qui change."""
        s = self._session(ident)
        case, fiches = self.affaire(s.affaire_id)
        if perso not in fiches:
            raise ErreurDeJeu(f"personnage inconnu : {perso}")
        question = (question or "").strip()[:QUESTION_MAX]
        if not question and not piece:
            raise ErreurDeJeu("posez une question ou montrez une pièce")
        if piece and piece not in s.partie.jeu.disponibles:
            raise ErreurDeJeu("cette pièce n'est pas dans votre dossier")
        if s.verdict and (s.verdict["juste"] or s.verdict.get("revele")):
            raise ErreurDeJeu("l'affaire est close")
        avant = set(s.partie.jeu.avoues.get(perso, []))
        with self._verrou_modele:
            reponse, nouvelles = s.partie.tour(perso, question, self.generer, piece=piece)
        s.questions += 1
        aveux = [x for x in s.partie.jeu.avoues.get(perso, []) if x not in avant]
        posee = s.partie.historiques[perso][-2]["content"]
        entree = None
        if aveux:
            pieces = {p["id"]: p for p in case["pieces"]}
            entree = {"perso": perso, "nom": fiches[perso]["nom"], "piece": pieces[piece]["nom"] if piece else None,
                      "texte": reponse, "numero": len(s.carnet) + 1}
            s.carnet.append(entree)
        nouvelles_pieces = [p for p in self._pieces(s) if p["id"] in nouvelles]
        # Le personnage ne remet pas toujours la pièce lui-même (une fouille, une déposition) : on raconte
        # comment elle arrive au dossier, juste après sa réplique.
        recits = [{"perso": perso, "apres": len(s.partie.historiques[perso]),
                   "texte": f"Nouvelle pièce au dossier : {p['nom'][0].lower() + p['nom'][1:]}"
                            + (f". Obtenue : {p['obtenue']}." if p["obtenue"] else ".")}
                  for p in nouvelles_pieces]
        s.recits += recits
        return {"perso": perso, "question": posee, "reponse": reponse, "aveu": bool(aveux), "carnet": entree,
                "nouvelles_pieces": nouvelles_pieces, "recits": recits, "progression": self._progression(s)}

    def reinitialiser(self, ident, perso):
        s = self._session(ident)
        if perso not in s.partie.historiques:
            raise ErreurDeJeu(f"personnage inconnu : {perso}")
        s.partie.reinitialiser(perso)
        s.recits = [r for r in s.recits if r["perso"] != perso]
        return {"perso": perso, "progression": self._progression(s)}

    def accuser(self, ident, perso, preuves=None):
        """Verdict et score. La solution n'est donnée que si l'accusation est juste (voir reveler)."""
        s = self._session(ident)
        case, fiches = self.affaire(s.affaire_id)
        if perso not in fiches:
            raise ErreurDeJeu(f"personnage inconnu : {perso}")
        jeu = s.partie.jeu
        juste = jeu.accuser(perso)
        preuves = preuves or {}
        pieces = {p["id"]: p for p in case["pieces"]}
        detail = []
        for cat in CATEGORIES:
            choisie = preuves.get(cat) or None
            if choisie not in jeu.disponibles:
                choisie = None
            detail.append({"categorie": cat, "piece": pieces[choisie]["nom"] if choisie else None,
                           "juste": bool(choisie) and choisie in case["preuves"][cat]})
        # Le score récompense l'enquête plus que le flair : les preuves décisives débloquées et les aveux
        # obtenus comptent autant que le nom du coupable.
        decisives = case["preuves"]["coupable"]
        reunies = sum(p in jeu.disponibles for p in decisives) / len(decisives)
        avouables = sum(1 for f in fiches.values() for x in f["secrets"] if x["revele_si"])
        obtenus = sum(len(v) for v in jeu.avoues.values()) / avouables
        score = (40 if juste else 0) + 8 * sum(d["juste"] for d in detail) + round(26 * reunies) + round(10 * obtenus)
        score = score if juste else min(score, 40)
        grade = next(nom for seuil, nom in GRADES if score >= seuil)
        s.verdict = {"juste": juste, "accuse": fiches[perso]["nom"], "score": score, "grade": grade,
                     "detail": detail, "questions": s.questions}
        if juste:
            s.verdict.update(self._solution(case))
        return dict(s.verdict)

    def reveler(self, ident):
        """Après une accusation fausse, le joueur peut demander la solution : la partie est alors finie."""
        s = self._session(ident)
        if not s.verdict:
            raise ErreurDeJeu("il faut d'abord accuser quelqu'un")
        case, _ = self.affaire(s.affaire_id)
        s.verdict.update(self._solution(case))
        s.verdict["revele"] = True
        return dict(s.verdict)

    def _solution(self, case):
        pieces = {p["id"]: p["nom"] for p in case["pieces"]}
        return {"coupable": case["personnages"][case["coupable"]], "aveu_final": case["aveu_final"],
                "solution": case["solution"], "mobile": case["mobile"], "moyen": case["moyen"],
                "opportunite": case["opportunite"],
                "preuves": {cat: [pieces[p] for p in liste] for cat, liste in case["preuves"].items()}}
