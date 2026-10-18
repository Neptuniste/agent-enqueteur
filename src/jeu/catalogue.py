"""Les affaires disponibles, et ce que le joueur a le droit d'en voir.

Une affaire est un sous-dossier de cases/ qui contient un case.json (format du cahier des charges, §7).
Rien de ce qui est renvoyé ici ne contient la solution, les secrets ni les rôles : seulement le dossier
public, les personnages tels que l'inspecteur les voit, et les pièces.
"""

import base64
import html
import re
from pathlib import Path

from src.game_state import charger_affaire

ROOT = Path(__file__).resolve().parents[2]
DOSSIER_AFFAIRES = ROOT / "cases"
AFFAIRE_PRINCIPALE = "main_case"

# Couleurs des médaillons, dans l'esprit des affiches des années 1920.
PALETTE = ["#7a2e2e", "#2f4f5f", "#5b4a2f", "#3e5641", "#6a3d5a", "#8a5a2b", "#33415c", "#5c3a21"]


def trouver_affaires(dossier=DOSSIER_AFFAIRES):
    """{id: chemin} des affaires disponibles ; l'affaire principale d'abord."""
    chemins = sorted(p.parent for p in Path(dossier).glob("*/case.json"))
    chemins.sort(key=lambda p: p.name != AFFAIRE_PRINCIPALE)
    affaires = {}
    for chemin in chemins:
        case, _ = charger_affaire(chemin)
        affaires[case["id"]] = chemin
    return affaires


def markdown_en_html(texte):
    """Rendu des documents du dossier (titres, citations, tableaux, gras, italique)."""
    try:
        from markdown_it import MarkdownIt
        return MarkdownIt("commonmark", {"html": False}).enable("table").render(texte)
    except ImportError:  # repli : le texte brut, lisible
        return f"<pre>{html.escape(texte)}</pre>"


def initiales(nom):
    return "".join(mot[0] for mot in nom.split() if mot[:1].isupper())[:2]


def portrait_svg(nom, indice):
    """Médaillon Art déco : buste en silhouette et initiales. Renvoie une data URI."""
    fond = PALETTE[indice % len(PALETTE)]
    chapeau = ("" if indice % 3 else
               '<path d="M58 44 Q80 30 102 44 L108 50 L52 50 Z" fill="#1b1612"/>')
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160">
  <defs><radialGradient id="g" cx="50%" cy="38%" r="70%">
    <stop offset="0" stop-color="{fond}" stop-opacity="0.95"/><stop offset="1" stop-color="#140f0c"/></radialGradient></defs>
  <circle cx="80" cy="80" r="76" fill="url(#g)" stroke="#c9a227" stroke-width="5"/>
  <circle cx="80" cy="80" r="68" fill="none" stroke="#c9a227" stroke-width="1.2" stroke-dasharray="3 4"/>
  <circle cx="80" cy="64" r="24" fill="#1b1612"/>{chapeau}
  <path d="M34 134 Q40 96 80 94 Q120 96 126 134 Z" fill="#1b1612"/>
  <rect x="40" y="118" width="80" height="24" rx="3" fill="#c9a227"/>
  <text x="80" y="136" text-anchor="middle" font-family="Georgia, serif" font-size="17" font-weight="bold"
        fill="#1b1612" letter-spacing="2">{html.escape(initiales(nom))}</text>
</svg>"""
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def accroche(case, phrases=2):
    """Les premières phrases du contexte public, pour la carte de l'affaire."""
    morceaux = re.split(r"(?<=[.!?])\s+", case["cadre"]["contexte_public"])
    return " ".join(morceaux[1:1 + phrases]) if len(morceaux) > phrases else case["cadre"]["contexte_public"]


def carte_affaire(case, fiches):
    """Ce qu'affiche l'écran de choix des enquêtes."""
    return {"id": case["id"], "titre": case["titre"], "lieu": case["cadre"]["lieu"], "date": case["cadre"]["date"],
            "accroche": accroche(case), "personnages": len(fiches), "pieces": len(case["pieces"]),
            "pieces_depart": sum(p["disponible_au_depart"] for p in case["pieces"])}


def piece_publique(piece, dossier):
    return {"id": piece["id"], "nom": piece["nom"][0].upper() + piece["nom"][1:], "description": piece["description"],
            "document": markdown_en_html((Path(dossier) / piece["document"]).read_text(encoding="utf-8")),
            "depart": piece["disponible_au_depart"]}


def personnage_public(fiche, indice):
    """L'identité et l'attitude : ce que voit l'inspecteur. Jamais le rôle ni les secrets."""
    return {"id": fiche["id"], "nom": fiche["nom"], "identite": fiche["identite"], "attitude": fiche["attitude"],
            "portrait": portrait_svg(fiche["nom"], indice)}


def dossier_public(case, fiches, dossier):
    """Tout le dossier de départ : contexte, victime, documents, personnages."""
    dossier = Path(dossier)
    documents = []
    for doc in case["documents"]:
        chemin = dossier / doc["fichier"]
        if chemin.suffix == ".svg":
            contenu = ('<img class="plan" alt="' + html.escape(doc["titre"]) + '" src="data:image/svg+xml;base64,'
                       + base64.b64encode(chemin.read_bytes()).decode("ascii") + '">')
            documents.append({"id": doc["id"], "titre": doc["titre"], "html": contenu, "plan": True})
        else:
            documents.append({"id": doc["id"], "titre": doc["titre"],
                              "html": markdown_en_html(chemin.read_text(encoding="utf-8")), "plan": False})
    ordre = sorted(fiches, key=lambda p: fiches[p]["nom"])
    return {**carte_affaire(case, fiches), "contexte": case["cadre"]["contexte_public"],
            "victime": {"nom": case["victime"]["nom"], "identite": case["victime"]["identite"]},
            "documents": documents,
            "personnages": [personnage_public(fiches[p], i) for i, p in enumerate(ordre)]}
