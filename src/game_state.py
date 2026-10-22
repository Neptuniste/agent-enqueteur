"""État d'une partie et chargement d'une affaire (cahier des charges, §4.2 et §7).

Le code garde la vérité : quelles pièces le joueur possède, ce qu'il a montré
à chaque personnage, et quels secrets ont déjà été avoués.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


def charger_affaire(dossier):
    """Charge case.json et les fiches de characters/. Renvoie (case, fiches par id)."""
    dossier = Path(dossier)
    case = json.loads((dossier / "case.json").read_text(encoding="utf-8"))
    fiches = {}
    for path in sorted((dossier / "characters").glob("*.json")):
        fiche = json.loads(path.read_text(encoding="utf-8"))
        fiches[fiche["id"]] = fiche
    return case, fiches


def texte_du_dossier(case, dossier, piece_ids):
    """Tout ce que le joueur peut lire : contexte, documents et pièces données.

    Sert au filtre de sortie : un mot déjà connu du joueur n'est pas une fuite.
    """
    dossier = Path(dossier)
    morceaux = [case["cadre"]["contexte_public"]]
    for doc in case["documents"]:
        morceaux.append((dossier / doc["fichier"]).read_text(encoding="utf-8"))
    pieces = {p["id"]: p for p in case["pieces"]}
    for piece_id in piece_ids:
        piece = pieces[piece_id]
        morceaux.append(piece["description"])
        morceaux.append((dossier / piece["document"]).read_text(encoding="utf-8"))
    return "\n".join(morceaux)


def obtention(document):
    """La ligne « **Obtenue** : … » du document d'une pièce (comment l'inspecteur l'a eue), sans le point final.

    Une pièce débloquée n'est pas toujours remise par le personnage (fouille, déposition) : les interfaces
    l'affichent avec l'annonce de la nouvelle pièce.
    """
    trouve = re.search(r"^\*\*Obtenue\*\*\s*:\s*(.+?)\.?\s*$", document, re.MULTILINE)
    return trouve.group(1) if trouve else None


def secrets_ouverts_par(fiche, piece_id):
    """Secrets de ce personnage que la pièce fait avouer (champ revele_si)."""
    return [s for s in fiche["secrets"] if piece_id in s["revele_si"]]


@dataclass
class GameState:
    case: dict
    fiches: dict
    disponibles: list = field(default_factory=list)
    montrees: dict = field(default_factory=dict)
    avoues: dict = field(default_factory=dict)
    accusation: str = None

    @classmethod
    def nouvelle_partie(cls, case, fiches):
        depart = [p["id"] for p in case["pieces"] if p["disponible_au_depart"]]
        return cls(case=case, fiches=fiches, disponibles=depart)

    def etat_pour(self, perso_id, piece_presentee=None):
        """État à passer à prompt_builder pour ce personnage et ce tour."""
        return {
            "secrets_avoues": list(self.avoues.get(perso_id, [])),
            "pieces_montrees": list(self.montrees.get(perso_id, [])),
            "piece_presentee": piece_presentee,
        }

    def presenter(self, perso_id, piece_id):
        """Le joueur montre une pièce à un personnage.

        Renvoie (etat_du_tour, nouvelles_pieces). etat_du_tour est calculé AVANT
        la mise à jour : c'est lui qui sert à construire le message système du tour.
        """
        if piece_id not in self.disponibles:
            raise ValueError(f"pièce non disponible : {piece_id}")
        etat = self.etat_pour(perso_id, piece_id)
        avoues = self.avoues.setdefault(perso_id, [])
        nouvelles = []
        for secret in secrets_ouverts_par(self.fiches[perso_id], piece_id):
            if secret["id"] in avoues:
                continue
            avoues.append(secret["id"])
            for p in secret["debloque"]:
                if p not in self.disponibles:
                    self.disponibles.append(p)
                    nouvelles.append(p)
        montrees = self.montrees.setdefault(perso_id, [])
        if piece_id not in montrees:
            montrees.append(piece_id)
        return etat, nouvelles

    def accuser(self, perso_id):
        """Enregistre l'accusation et renvoie True si c'est le coupable."""
        self.accusation = perso_id
        return perso_id == self.case["coupable"]
