"""Portraits des personnages : médaillons Art déco dessinés en SVG, à partir de traits décrits en JSON.

Chaque affaire peut fournir cases/<affaire>/portraits.json : {"<id du personnage>": {traits}}. Les traits
(coiffure, chapeau, vêtement, expression, accessoires) ne disent rien des secrets : ce sont des indices
visibles de tous, comme l'attitude de la fiche. Sans fichier, le jeu garde le médaillon à initiales.

    python -m src.jeu.portraits cases/main_case   # planche de contrôle, dans le dossier temporaire
"""

import base64
import html
import json
import tempfile
import sys
from pathlib import Path

ENCRE = "#1b1612"
OR = "#c9a227"
PEAUX = {"claire": "#f1d3b6", "rosee": "#ecc3a3", "doree": "#e2b48d", "mate": "#cf9b74", "halee": "#c08a63"}
CHEVEUX = {"noir": "#1f1a17", "brun": "#3e2a1e", "chatain": "#6b4a2f", "auburn": "#86401f", "blond": "#d0a85a",
           "gris": "#8f8a84", "poivre_sel": "#5d5853", "blanc": "#dcd7cf", "argent": "#b9b6b0"}


def assombrir(couleur, facteur=0.75):
    r, g, b = (int(couleur[i:i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{int(v * facteur):02x}" for v in (r, g, b))


# --- Éléments du dessin (repère 160 × 160, visage centré en 80, 68) -------------------------------------

def fond(couleur):
    rayons = "".join(
        f'<path d="M80 172 L{80 + 150 * dx:.1f} {172 - 150 * dy:.1f} L{80 + 150 * ex:.1f} {172 - 150 * ey:.1f} Z" '
        f'fill="#fff" opacity="0.05"/>'
        for dx, dy, ex, ey in ((-0.95, 0.31, -0.8, 0.6), (-0.6, 0.8, -0.35, 0.94), (-0.1, 1, 0.1, 1),
                               (0.35, 0.94, 0.6, 0.8), (0.8, 0.6, 0.95, 0.31)))
    return (f'<circle cx="80" cy="80" r="72" fill="url(#fond)"/>{rayons}'
            f'<radialGradient id="fond" cx="50%" cy="34%" r="72%"><stop offset="0" stop-color="{couleur}"/>'
            f'<stop offset="1" stop-color="{assombrir(couleur, 0.35)}"/></radialGradient>')


def buste(v):
    """Vêtement : forme des épaules, puis détails du col."""
    c = v.get("couleur", "#2b2b33")
    sombre = assombrir(c, 0.7)
    forme = v.get("forme", "costume")
    epaules = (f'<path d="M12 168 C16 128 46 115 80 113 C114 115 144 128 148 168 Z" fill="{c}" '
               f'stroke="{ENCRE}" stroke-width="1.2"/>')
    peau = v["_peau"]
    cou = (f'<path d="M71 86 L71 108 Q80 116 89 108 L89 86 Z" fill="{peau}"/>'
           f'<path d="M71 96 Q80 104 89 96 L89 99 Q80 108 71 99 Z" fill="{assombrir(peau, 0.85)}" opacity="0.7"/>')
    morceaux = []
    if forme in ("costume", "redingote", "veste_travail", "tailleur", "gilet_barman", "uniforme"):
        chemise = v.get("chemise", "#f2eee6")
        if forme == "gilet_barman":
            epaules = (f'<path d="M12 168 C16 128 46 115 80 113 C114 115 144 128 148 168 Z" fill="{chemise}" '
                       f'stroke="{ENCRE}" stroke-width="1.2"/>'
                       f'<path d="M46 168 L56 124 L72 112 L80 132 L88 112 L104 124 L114 168 Z" fill="{c}" '
                       f'stroke="{ENCRE}" stroke-width="1"/>')
            morceaux.append(f'<path d="M72 112 L80 132 L88 112 L84 108 L80 112 L76 108 Z" fill="{chemise}"/>')
            for y in (138, 148, 158):
                morceaux.append(f'<circle cx="80" cy="{y}" r="1.4" fill="{OR}"/>')
        else:
            morceaux.append(f'<path d="M66 110 L80 146 L94 110 L88 106 L80 114 L72 106 Z" fill="{chemise}"/>')
            revers = sombre if forme != "veste_travail" else assombrir(c, 0.85)
            morceaux.append(f'<path d="M64 110 L80 150 L70 168 L48 168 L58 120 Z" fill="{revers}" opacity="0.55"/>'
                            f'<path d="M96 110 L80 150 L90 168 L112 168 L102 120 Z" fill="{revers}" opacity="0.55"/>'
                            f'<path d="M66 110 L80 150 M94 110 L80 150" stroke="{ENCRE}" stroke-width="1" fill="none"/>')
            if v.get("croise"):
                for x, y in ((74, 152), (86, 152), (74, 162), (86, 162)):
                    morceaux.append(f'<circle cx="{x}" cy="{y}" r="1.6" fill="{sombre}" stroke="{ENCRE}" stroke-width="0.5"/>')
            if v.get("gilet"):
                morceaux.append(f'<path d="M72 120 L80 146 L88 120 L92 168 L68 168 Z" fill="{v["gilet"]}" '
                                f'stroke="{ENCRE}" stroke-width="0.8"/>')
    elif forme == "robe_col_haut":
        morceaux.append(f'<path d="M68 92 Q80 100 92 92 L93 112 Q80 118 67 112 Z" fill="{c}" stroke="{ENCRE}" stroke-width="1"/>')
        for y in (124, 134, 144, 154):
            morceaux.append(f'<circle cx="80" cy="{y}" r="1.3" fill="{sombre}" stroke="{ENCRE}" stroke-width="0.4"/>')
        cou = f'<path d="M71 86 L71 98 L89 98 L89 86 Z" fill="{peau}"/>'
    elif forme == "robe_soiree":
        epaules = (f'<path d="M12 168 C16 128 46 115 80 113 C114 115 144 128 148 168 Z" fill="{peau}" '
                   f'stroke="{ENCRE}" stroke-width="1"/>'
                   f'<path d="M30 168 Q40 134 58 128 Q80 150 102 128 Q120 134 130 168 Z" fill="{c}" '
                   f'stroke="{ENCRE}" stroke-width="1"/>')
        morceaux.append(f'<path d="M58 128 L62 114 M102 128 L98 114" stroke="{c}" stroke-width="2.4"/>')
        for i in range(14):
            morceaux.append(f'<circle cx="{36 + i * 6.6:.1f}" cy="{150 + (i % 3) * 5}" r="0.9" fill="#fff6d8" opacity="0.8"/>')
    elif forme == "robe_elegante":
        epaules = (f'<path d="M12 168 C16 128 46 115 80 113 C114 115 144 128 148 168 Z" fill="{c}" '
                   f'stroke="{ENCRE}" stroke-width="1.2"/>'
                   f'<path d="M64 112 L80 138 L96 112 Q80 116 64 112 Z" fill="{peau}"/>')
    elif forme == "costume_scene":
        morceaux.append(f'<path d="M80 110 Q68 118 72 128 Q62 132 70 142 Q64 148 74 152 L86 152 Q96 148 90 142 '
                        f'Q98 132 88 128 Q92 118 80 110 Z" fill="#f4efe4" stroke="{ENCRE}" stroke-width="0.9"/>')
        morceaux.append(f'<path d="M30 150 L58 126 M130 150 L102 126" stroke="{OR}" stroke-width="1.5"/>')
    elif forme == "cardigan":
        morceaux.append(f'<path d="M64 110 Q72 120 80 112 Q88 120 96 110 L94 106 L80 110 L66 106 Z" fill="#f4efe4" '
                        f'stroke="{ENCRE}" stroke-width="0.8"/>'
                        f'<path d="M62 112 L76 168 M98 112 L84 168" stroke="{sombre}" stroke-width="3"/>')
        for y in (130, 142, 154):
            morceaux.append(f'<circle cx="80" cy="{y}" r="1.3" fill="#f4efe4"/>')
    elif forme == "manteau_fourrure":
        morceaux.append(f'<path d="M66 112 L80 150 L94 112 Q80 118 66 112 Z" fill="{v.get("dessous", "#c8a2c8")}"/>')
        for i in range(10):
            morceaux.append(f'<circle cx="{82 + (i % 2) * 2}" cy="{120 + i * 3}" r="0.8" fill="#fff6d8"/>')
    col = v.get("col")
    if col == "noeud":
        nc = v.get("noeud", ENCRE)
        morceaux.append(f'<path d="M80 113 L70 108 L70 118 Z M80 113 L90 108 L90 118 Z" fill="{nc}" '
                        f'stroke="{ENCRE}" stroke-width="0.6"/><circle cx="80" cy="113" r="2" fill="{nc}"/>')
    elif col == "cravate":
        nc = v.get("cravate", "#6a1f1f")
        morceaux.append(f'<path d="M77 111 L83 111 L82 116 L85 140 L80 146 L75 140 L78 116 Z" fill="{nc}" '
                        f'stroke="{ENCRE}" stroke-width="0.6"/>')
    elif col == "foulard":
        nc = v.get("foulard", "#a02a22")
        morceaux.append(f'<path d="M66 106 Q80 120 94 106 L96 112 Q80 126 64 112 Z" fill="{nc}" '
                        f'stroke="{ENCRE}" stroke-width="0.7"/><path d="M84 116 L90 132 L82 128 Z" fill="{nc}"/>')
    elif col == "lavalliere":
        nc = v.get("cravate", "#efe6d2")
        morceaux.append(f'<path d="M73 110 Q80 118 87 110 L88 124 Q80 128 72 124 Z" fill="{nc}" '
                        f'stroke="{ENCRE}" stroke-width="0.6"/><circle cx="80" cy="117" r="1.4" fill="{OR}"/>')
    if v.get("fourrure"):
        f = v["fourrure"]
        morceaux.append(f'<path d="M14 150 Q24 118 60 112 Q66 124 54 136 Q40 146 30 168 L12 168 Z" fill="{f}" '
                        f'stroke="{ENCRE}" stroke-width="0.8"/>'
                        f'<path d="M146 150 Q136 118 100 112 Q94 124 106 136 Q120 146 130 168 L148 168 Z" fill="{f}" '
                        f'stroke="{ENCRE}" stroke-width="0.8"/>')
        for x, y in ((30, 140), (40, 128), (120, 140), (110, 128), (24, 156), (136, 156)):
            morceaux.append(f'<path d="M{x} {y} q3 -3 6 0" stroke="{assombrir(f, 0.7)}" stroke-width="1" fill="none"/>')
    return cou + epaules + "".join(morceaux)


def tete(peau, oreilles=True):
    contour = f'stroke="{ENCRE}" stroke-width="1.1"'
    o = (f'<ellipse cx="60.5" cy="70" rx="3.6" ry="6" fill="{peau}" {contour}/>'
         f'<ellipse cx="99.5" cy="70" rx="3.6" ry="6" fill="{peau}" {contour}/>') if oreilles else ""
    return o + f'<ellipse cx="80" cy="68" rx="19.5" ry="24" fill="{peau}" {contour}/>'


def sourcils(expr, couleur, epais=1.6):
    formes = {
        "neutre": ("M68 62.5 Q72 60.5 76 62", "M84 62 Q88 60.5 92 62.5"),
        "fronces": ("M68 61 Q72 61.5 76.5 64", "M83.5 64 Q88 61.5 92 61"),
        "inquiets": ("M68 63.5 Q72 61.5 76 60.5", "M84 60.5 Q88 61.5 92 63.5"),
        "hausse": ("M68 62.5 Q72 60.5 76 62", "M84 59.5 Q88 57 92 59.5"),
        "arques": ("M68 62 Q72 58.5 76 61", "M84 61 Q88 58.5 92 62"),
        "durs": ("M67.5 61.5 L76.5 63.5", "M83.5 63.5 L92.5 61.5"),
    }
    g, d = formes[expr]
    return "".join(f'<path d="{p}" stroke="{couleur}" stroke-width="{epais}" fill="none" stroke-linecap="round"/>'
                   for p in (g, d))


def yeux(expr, femme=False, regard=0.0):
    if expr == "baisses":
        traits = "".join(f'<path d="M{x - 3} 68.5 Q{x} 70.5 {x + 3} 68.5" stroke="{ENCRE}" stroke-width="1.3" fill="none"/>'
                         for x in (72.5, 87.5))
    elif expr == "plisses":
        traits = "".join(f'<path d="M{x - 3} 69 Q{x} 66.5 {x + 3} 69" stroke="{ENCRE}" stroke-width="1.4" fill="none"/>'
                         for x in (72.5, 87.5))
    else:
        ry = 2.5 if expr == "grands" else 2.1
        traits = "".join(
            f'<ellipse cx="{x}" cy="68.5" rx="3.1" ry="{ry}" fill="#fbf7ef"/>'
            f'<circle cx="{x + regard:.1f}" cy="68.6" r="1.7" fill="{ENCRE}"/>'
            f'<circle cx="{x + regard + 0.6:.1f}" cy="68" r="0.5" fill="#fff"/>' for x in (72.5, 87.5))
    if femme:
        traits += "".join(f'<path d="M{x - 3.4} 67.2 Q{x} 65 {x + 3.6} 66.8" stroke="{ENCRE}" stroke-width="1.2" '
                          f'fill="none"/>' for x in (72.5, 87.5))
    return traits


def nez(peau, rouge=False):
    t = f'<path d="M80.5 70 Q78.6 76.5 77.6 78.4 Q79.6 80 82.4 78.8" stroke="{assombrir(peau, 0.72)}" stroke-width="1.1" fill="none"/>'
    if rouge:
        t += '<ellipse cx="80" cy="78" rx="3.4" ry="2.6" fill="#c0392b" opacity="0.35"/>'
    return t


def bouche(expr, levres=None):
    if expr == "rire":
        return ('<path d="M72.5 82.5 Q80 92 87.5 82.5 Z" fill="#6b1d1d" stroke="#1b1612" stroke-width="0.9"/>'
                '<path d="M74 83.2 L86 83.2 L85 85.2 L75 85.2 Z" fill="#fbf7ef"/>')
    formes = {"sourire": "M74 83.5 Q80 88 86 83.5", "neutre": "M75.5 84.5 Q80 85.6 84.5 84.5",
              "serree": "M76 84.8 L84 84.8", "moue": "M75 84.5 Q80 85.4 86 82.4",
              "triste": "M75 86 Q80 83.6 85 86", "ouverte": "M76 84 Q80 88 84 84 Q80 85.2 76 84 Z"}
    if levres:
        haut = {"sourire": "M74 83.2 Q77 81.6 80 82.6 Q83 81.6 86 83.2 Q80 84.4 74 83.2 Z",
                "moue": "M74.6 84 Q77.4 82.4 80 83.2 Q83 81.4 86 82.2 Q80 84.8 74.6 84 Z"}.get(
            expr, "M75 84 Q77.6 82.4 80 83.4 Q82.4 82.4 85 84 Q80 85 75 84 Z")
        bas = {"sourire": "M74 83.2 Q80 88.2 86 83.2 Q80 85 74 83.2 Z"}.get(expr, "M75 84 Q80 87.6 85 84 Q80 85.4 75 84 Z")
        return f'<path d="{haut}" fill="{levres}"/><path d="{bas}" fill="{levres}"/>'
    remplir = 'fill="#6b1d1d"' if expr == "ouverte" else 'fill="none"'
    return f'<path d="{formes[expr]}" stroke="{ENCRE}" stroke-width="1.3" {remplir} stroke-linecap="round"/>'


def rides(peau, age):
    if age < 45:
        return ""
    c = assombrir(peau, 0.7)
    t = (f'<path d="M73 77 Q71 82 73.5 86 M87 77 Q89 82 86.5 86" stroke="{c}" stroke-width="0.9" fill="none" opacity="0.8"/>')
    if age >= 55:
        t += (f'<path d="M72 54 Q80 52 88 54 M74 57.5 Q80 56 86 57.5" stroke="{c}" stroke-width="0.8" fill="none" opacity="0.7"/>'
              f'<path d="M66 70 l-2 1.2 M94 70 l2 1.2" stroke="{c}" stroke-width="0.8" opacity="0.8"/>')
    return t


def joues(couleur="#d9534f", force=0.18):
    return (f'<ellipse cx="69.5" cy="77" rx="3.8" ry="2.2" fill="{couleur}" opacity="{force}"/>'
            f'<ellipse cx="90.5" cy="77" rx="3.8" ry="2.2" fill="{couleur}" opacity="{force}"/>')


def cheveux_arriere(style, c):
    contour = f'stroke="{ENCRE}" stroke-width="1"'
    formes = {
        "carre": f'<path d="M55 96 Q51 44 80 41 Q109 44 105 96 Q99 99 94 94 L66 94 Q61 99 55 96 Z" fill="{c}" {contour}/>',
        "ondule": f'<path d="M55 94 Q51 44 80 41 Q109 44 105 94 Q98 98 93 92 L67 92 Q62 98 55 94 Z" fill="{c}" {contour}/>',
        "boucles": "".join(f'<circle cx="{x}" cy="{y}" r="8.5" fill="{c}" {contour}/>' for x, y in
                           ((58, 58), (56, 74), (59, 89), (102, 58), (104, 74), (101, 89), (66, 44), (80, 40), (94, 44))),
        "defaits": f'<path d="M54 112 Q46 70 58 50 Q72 36 92 40 Q112 48 108 80 Q112 100 104 116 Q96 104 98 90 '
                   f'L62 90 Q64 106 54 112 Z" fill="{c}" {contour}/>',
        "longs_ondules": f'<path d="M56 104 Q50 56 66 44 Q80 36 96 44 Q110 56 104 104 Q98 108 94 100 L66 100 '
                         f'Q62 108 56 104 Z" fill="{c}" {contour}/>',
    }
    return formes.get(style, "")


def cheveux_avant(style, c, meche=None):
    contour = f'stroke="{ENCRE}" stroke-width="1"'
    clair = assombrir(c, 1.25) if c != CHEVEUX["noir"] else "#3a332e"
    formes = {
        "plaque": f'<path d="M60 66 Q58 42 80 41.5 Q102 42 100 66 Q98 52 90 49 Q80 46 70 49 Q62 52 60 66 Z" fill="{c}" {contour}/>'
                  f'<path d="M66 50 Q80 45 94 50" stroke="{clair}" stroke-width="1" fill="none"/>',
        "raie": f'<path d="M60 68 Q57 42 80 41.5 Q103 42 100 68 Q99 54 93 50 Q86 47 74 52 Q68 50 64 56 Q61 60 60 68 Z" '
                f'fill="{c}" {contour}/><path d="M74 44 L72 52" stroke="{clair}" stroke-width="1"/>',
        "degarni": f'<path d="M60 76 Q57 62 61 56 Q63 64 64 72 Z" fill="{c}" {contour}/>'
                   f'<path d="M100 76 Q103 62 99 56 Q97 64 96 72 Z" fill="{c}" {contour}/>'
                   f'<path d="M72 47 Q80 45.5 88 47" stroke="{c}" stroke-width="1.4" fill="none" opacity="0.8"/>',
        "court": f'<path d="M60.5 64 Q59 43 80 42 Q101 43 99.5 64 Q97 50 80 48 Q63 50 60.5 64 Z" fill="{c}" {contour}/>',
        "argent_peigne": f'<path d="M60 68 Q57 41 80 41 Q103 41 100 68 Q98 52 88 49 Q76 46 66 52 Q61 58 60 68 Z" '
                         f'fill="{c}" {contour}/><path d="M68 47 Q80 43 95 50 M70 51 Q82 47 96 55" '
                         f'stroke="{assombrir(c, 0.8)}" stroke-width="0.9" fill="none"/>',
        "carre": f'<path d="M60 63 Q61 44 80 44 Q99 44 100 63 Q92 54 80 55 Q68 54 60 63 Z" fill="{c}" {contour}/>',
        "ondule": f'<path d="M60 66 Q60 44 82 44 Q100 46 100 64 Q94 54 86 56 Q78 52 70 58 Q64 58 60 66 Z" fill="{c}" {contour}/>'
                  f'<path d="M58 72 Q62 68 58 64 M102 72 Q98 68 102 64 M66 52 Q72 48 78 52 Q84 48 90 52" '
                  f'stroke="{clair}" stroke-width="1.2" fill="none"/>',
        "chignon": f'<circle cx="80" cy="40" r="9" fill="{c}" {contour}/>'
                   f'<path d="M60 68 Q58 44 80 43 Q102 44 100 68 Q96 52 80 50 Q64 52 60 68 Z" fill="{c}" {contour}/>',
        "chignon_haut": f'<ellipse cx="80" cy="37" rx="11" ry="8" fill="{c}" {contour}/>'
                        f'<path d="M60 68 Q58 42 80 42 Q102 42 100 68 Q96 50 80 49 Q64 50 60 68 Z" fill="{c}" {contour}/>'
                        f'<path d="M70 37 Q80 32 90 37" stroke="{assombrir(c, 0.8)}" stroke-width="1" fill="none"/>',
        "boucles": "".join(f'<circle cx="{x}" cy="{y}" r="6.5" fill="{c}" {contour}/>' for x, y in
                           ((64, 52), (73, 47), (83, 46), (93, 50), (99, 58), (61, 60))),
        "defaits": f'<path d="M60 66 Q58 44 80 43 Q102 44 100 66 Q94 54 86 55 Q80 50 72 56 Q64 56 60 66 Z" fill="{c}" {contour}/>'
                   f'<path d="M74 50 Q70 60 72 66 M86 52 Q90 58 88 64 M64 58 Q60 66 63 74" stroke="{c}" '
                   f'stroke-width="1.6" fill="none"/>',
        "longs_ondules": f'<path d="M60 68 Q56 42 80 41 Q104 42 100 68 Q98 52 86 50 Q76 48 70 56 Q74 60 68 64 Q62 62 60 68 Z" '
                         f'fill="{c}" {contour}/>',
        "militaire": f'<path d="M61 60 Q61 44 80 43.5 Q99 44 99 60 Q96 50 80 49 Q64 50 61 60 Z" fill="{c}" {contour}/>',
    }
    t = formes.get(style, "")
    if meche:
        t += f'<path d="M84 44 Q88 50 90 58" stroke="{meche}" stroke-width="2.2" fill="none"/>'
    return t


def pilosite(style, c):
    contour = f'stroke="{ENCRE}" stroke-width="0.7"'
    formes = {
        "crayon": f'<path d="M74.5 81.2 Q80 79.6 85.5 81.2" stroke="{c}" stroke-width="1.6" fill="none"/>',
        "fine": f'<path d="M74 81.4 Q77 79.6 80 80.8 Q83 79.6 86 81.4" stroke="{c}" stroke-width="2" fill="none"/>',
        "morse": f'<path d="M71 85 Q72 78 80 79.5 Q88 78 89 85 Q85 82.6 80 84 Q75 82.6 71 85 Z" fill="{c}" {contour}/>',
        "guidon": f'<path d="M80 80.5 Q74 79 70 81 Q67 81 66.5 78.5 Q70 82.5 80 80.5 Q90 82.5 93.5 78.5 Q93 81 90 81 Q86 79 80 80.5 Z" '
                  f'fill="{c}" {contour}/>',
        "barbe_courte": f'<path d="M66 82 Q68 97 80 99 Q92 97 94 82 Q90 90.5 80 90 Q70 90.5 66 82 Z" fill="{c}" '
                        f'stroke="{assombrir(c, 0.75)}" stroke-width="0.8"/>'
                        f'<path d="M74.5 81.4 Q80 79.4 85.5 81.4" stroke="{c}" stroke-width="2.2" fill="none"/>',
        "bouc": f'<path d="M77 88 Q80 98 83 88 Z" fill="{c}" {contour}/>'
                f'<path d="M73 81.6 Q76 79 80 80.6 Q84 79 87 81.6 Q90 80 91 77" stroke="{c}" stroke-width="1.8" fill="none"/>',
        "trois_jours": '<path d="M63 74 Q64 94 80 96 Q96 94 97 74 Q94 88 80 90 Q66 88 63 74 Z" fill="#5d5853" opacity="0.28"/>',
    }
    return formes.get(style, "")


def lunettes(style):
    if style == "rondes":
        return (f'<circle cx="72.5" cy="68.5" r="5" fill="#fff" fill-opacity="0.12" stroke="{OR}" stroke-width="1.2"/>'
                f'<circle cx="87.5" cy="68.5" r="5" fill="#fff" fill-opacity="0.12" stroke="{OR}" stroke-width="1.2"/>'
                f'<path d="M77.5 68.5 Q80 67 82.5 68.5 M67.5 68 L61 67 M92.5 68 L99 67" stroke="{OR}" stroke-width="1"/>')
    if style == "lorgnon":
        return (f'<ellipse cx="73" cy="70" rx="4.6" ry="3.8" fill="#fff" fill-opacity="0.12" stroke="{OR}" stroke-width="1"/>'
                f'<ellipse cx="87" cy="70" rx="4.6" ry="3.8" fill="#fff" fill-opacity="0.12" stroke="{OR}" stroke-width="1"/>'
                f'<path d="M77.6 69.6 Q80 68 82.4 69.6 M91.6 70.5 Q102 86 96 112" stroke="{OR}" stroke-width="0.8" fill="none"/>')
    if style == "monocle":
        return (f'<circle cx="87.5" cy="68.5" r="5.2" fill="#fff" fill-opacity="0.15" stroke="{OR}" stroke-width="1.4"/>'
                f'<path d="M92.5 70 Q100 90 94 114" stroke="{OR}" stroke-width="0.8" fill="none"/>')
    return ""


def chapeau(style, c, ruban=None):
    contour = f'stroke="{ENCRE}" stroke-width="1.1"'
    ruban = ruban or assombrir(c, 0.55)
    if style == "feutre":
        return (f'<path d="M62 50 Q60 30 72 27 Q80 31 88 27 Q100 30 98 50 Z" fill="{c}" {contour}/>'
                f'<path d="M62.4 44 L97.6 44 L98 50 L62 50 Z" fill="{ruban}"/>'
                f'<path d="M42 52 Q80 40 118 52 Q112 58 98 52 Q80 48 62 52 Q48 58 42 52 Z" fill="{c}" {contour}/>')
    if style == "melon":
        return (f'<path d="M61 50 Q60 28 80 27 Q100 28 99 50 Z" fill="{c}" {contour}/>'
                f'<path d="M61.5 45 L98.5 45 L99 50 L61 50 Z" fill="{ruban}"/>'
                f'<path d="M54 51 Q80 44 106 51 Q104 55 98 53 Q80 50 62 53 Q56 55 54 51 Z" fill="{c}" {contour}/>')
    if style == "cloche":
        return (f'<path d="M56 66 Q52 36 80 33 Q108 36 104 66 Q96 60 80 60 Q64 60 56 66 Z" fill="{c}" {contour}/>'
                f'<path d="M57 58 Q80 52 103 58 L103.6 62 Q80 56 56.4 62 Z" fill="{ruban}"/>'
                f'<circle cx="97" cy="57" r="3.6" fill="{OR}" {contour}/>')
    if style == "bandeau_plume":
        return (f'<path d="M59 56 Q80 50 101 56 L101 60 Q80 54 59 60 Z" fill="{c}" {contour}/>'
                f'<circle cx="66" cy="57" r="2.6" fill="#fff6d8" {contour}/>'
                f'<path d="M64 56 Q50 30 62 14 Q60 34 70 52" fill="{ruban}" stroke="{ENCRE}" stroke-width="0.8"/>'
                f'<path d="M64 52 Q58 34 62 18" stroke="{ENCRE}" stroke-width="0.7" fill="none"/>')
    if style == "casquette":
        return (f'<path d="M59 56 Q58 36 80 35 Q104 36 102 54 Q90 50 80 51 Q70 51 59 56 Z" fill="{c}" {contour}/>'
                f'<path d="M58 56 Q72 49 96 52 Q102 56 94 60 Q74 58 58 56 Z" fill="{assombrir(c, 0.8)}" {contour}/>'
                f'<circle cx="80" cy="36.5" r="1.8" fill="{assombrir(c, 0.7)}"/>')
    if style == "voilette":
        filet = "".join(f'<path d="M{60 + i * 4} 52 L{58 + i * 4} 76" stroke="{ENCRE}" stroke-width="0.4" opacity="0.6"/>'
                        for i in range(11))
        filet += "".join(f'<path d="M57 {56 + i * 4} L103 {56 + i * 4}" stroke="{ENCRE}" stroke-width="0.4" opacity="0.6"/>'
                         for i in range(5))
        return (f'<path d="M64 46 Q66 32 84 33 Q100 35 100 48 Z" fill="{c}" {contour}/>'
                f'<path d="M86 34 Q96 22 104 30 Q96 32 92 38 Z" fill="{ruban}" {contour}/>'
                f'<path d="M58 50 Q80 44 102 50 L103 74 Q80 78 57 74 Z" fill="{ENCRE}" opacity="0.12"/>{filet}')
    if style == "diademe":
        return (f'<path d="M64 46 L68 38 L72 44 L76 34 L80 42 L84 34 L88 44 L92 38 L96 46 Q80 42 64 46 Z" fill="{OR}" '
                f'{contour}/><circle cx="80" cy="40" r="1.8" fill="#e8f4ff"/><circle cx="72" cy="42" r="1.1" fill="#e8f4ff"/>'
                f'<circle cx="88" cy="42" r="1.1" fill="#e8f4ff"/>')
    if style == "peigne":
        return f'<path d="M92 40 Q100 34 106 42 L102 46 Q98 40 94 44 Z" fill="{OR}" {contour}/>'
    return ""


def accessoires(liste, v):
    t = []
    for a in liste:
        if a == "boucle_unique":       # une seule boucle d'oreille de strass, à l'oreille droite du portrait
            t.append(f'<path d="M99.5 76 L101.8 80 L99.5 84.5 L97.2 80 Z" fill="#eaf6ff" stroke="{ENCRE}" stroke-width="0.6"/>')
        elif a == "perles_oreilles":
            t.append('<circle cx="60.5" cy="78" r="1.8" fill="#f4f1ea"/><circle cx="99.5" cy="78" r="1.8" fill="#f4f1ea"/>')
        elif a == "collier_perles":
            t.append("".join(f'<circle cx="{64 + i * 2.9:.1f}" cy="{112 + 6 * (1 - ((i - 5.5) / 5.5) ** 2):.1f}" r="1.5" '
                             f'fill="#f4f1ea" stroke="#b8b2a6" stroke-width="0.3"/>' for i in range(12)))
        elif a == "sautoir":
            t.append(f'<path d="M66 112 Q80 168 94 112" stroke="#f4f1ea" stroke-width="2" stroke-dasharray="0.1 3.2" '
                     f'stroke-linecap="round" fill="none"/>')
        elif a == "epingles_rouges":    # les épingles de couturière au revers, rouge vif
            for x, y in ((60, 124), (64, 130), (57, 132)):
                t.append(f'<path d="M{x} {y} L{x + 7} {y - 5}" stroke="#d6d2c8" stroke-width="0.9"/>'
                         f'<circle cx="{x}" cy="{y}" r="2" fill="#d1202a" stroke="{ENCRE}" stroke-width="0.4"/>')
        elif a == "oeillet":
            t.append(f'<circle cx="104" cy="126" r="4" fill="#c0262d" stroke="{ENCRE}" stroke-width="0.6"/>'
                     f'<path d="M101 124 Q104 128 107 124 M102 128 Q104 125 106 128" stroke="#8a1218" stroke-width="0.7" fill="none"/>'
                     f'<path d="M104 130 L103 136" stroke="#2f5a2a" stroke-width="1.2"/>')
        elif a == "papillon":
            t.append(f'<path d="M104 126 Q96 118 98 128 Q96 136 104 128 Q112 136 110 128 Q112 118 104 126 Z" fill="#3f7fbf" '
                     f'stroke="{ENCRE}" stroke-width="0.6"/><path d="M104 122 L104 132" stroke="{ENCRE}" stroke-width="0.8"/>')
        elif a == "rosette":
            t.append(f'<circle cx="103" cy="126" r="2.6" fill="#c0262d" stroke="{ENCRE}" stroke-width="0.5"/>')
        elif a == "chaine_montre":
            t.append(f'<path d="M70 142 Q80 154 92 144" stroke="{OR}" stroke-width="1.4" fill="none"/>'
                     f'<circle cx="92" cy="144" r="2.4" fill="{OR}" stroke="{ENCRE}" stroke-width="0.5"/>')
        elif a == "carnet":             # le carnet que Céleste serre contre elle
            t.append(f'<g transform="rotate(-12 50 146)"><rect x="38" y="132" width="24" height="30" rx="2" fill="#2a1f1a" '
                     f'stroke="{ENCRE}" stroke-width="0.9"/><path d="M41 132 L41 162" stroke="{OR}" stroke-width="0.8"/>'
                     f'<path d="M38 150 L62 150" stroke="#8a1218" stroke-width="1.2"/></g>')
        elif a == "livre_caisse":
            t.append(f'<g transform="rotate(8 112 146)"><rect x="98" y="130" width="30" height="34" rx="2" fill="#5a1e1e" '
                     f'stroke="{ENCRE}" stroke-width="0.9"/><rect x="104" y="138" width="18" height="7" fill="{OR}" opacity="0.8"/></g>')
        elif a == "trousse":
            t.append(f'<path d="M100 140 Q100 132 112 132 Q124 132 124 140 L126 164 L98 164 Z" fill="#141010" '
                     f'stroke="#6d6458" stroke-width="0.9"/><path d="M106 132 Q112 124 118 132" stroke="#6d6458" '
                     f'stroke-width="1.6" fill="none"/><rect x="110" y="138" width="4" height="3" fill="{OR}"/>')
        elif a == "torchon":            # le torchon du barman, sur l'épaule
            t.append(f'<path d="M98 116 Q112 116 120 124 L124 152 Q116 150 112 154 L106 128 Z" fill="#f4efe4" '
                     f'stroke="{ENCRE}" stroke-width="0.8"/><path d="M110 126 L116 150 M114 124 L120 148" stroke="#b33a3a" stroke-width="1"/>')
        elif a == "canne":              # le pommeau d'argent de la canne
            t.append(f'<path d="M118 168 L114 140" stroke="#2a1f1a" stroke-width="3.4"/>'
                     f'<ellipse cx="113.6" cy="137" rx="4.2" ry="3.4" fill="#d7d9dc" stroke="{ENCRE}" stroke-width="0.7"/>')
        elif a == "camee":
            t.append(f'<ellipse cx="80" cy="104" rx="3.6" ry="4.4" fill="#f0dcc0" stroke="{OR}" stroke-width="1.2"/>')
        elif a == "grain_beaute":
            t.append(f'<circle cx="88" cy="81" r="0.9" fill="{ENCRE}"/>')
        elif a == "feuillets":          # le texte de la pièce que tient la souffleuse
            t.append(f'<g transform="rotate(-8 48 148)"><rect x="34" y="134" width="26" height="32" fill="#f4efe4" '
                     f'stroke="{ENCRE}" stroke-width="0.8"/>' + "".join(
                         f'<path d="M38 {140 + i * 4} L56 {140 + i * 4}" stroke="#8f8a84" stroke-width="0.7"/>' for i in range(6))
                     + "</g>")
    return "".join(t)


def dessiner(traits, nom=""):
    """SVG complet d'un portrait. `traits` : voir les fichiers cases/<affaire>/portraits.json."""
    peau = PEAUX.get(traits.get("peau", "rosee"), traits.get("peau"))
    cheveux = CHEVEUX.get(traits.get("cheveux", "brun"), traits.get("cheveux"))
    femme = traits.get("femme", False)
    v = dict(traits.get("vetement", {}), _peau=peau)
    coiffure = traits.get("coiffure", "court")
    expr = traits.get("expression", {})
    contenu = [
        fond(traits.get("fond", "#33415c")),
        cheveux_arriere(coiffure, cheveux),
        buste(v),
        tete(peau, oreilles=coiffure not in ("carre", "ondule", "boucles", "defaits", "longs_ondules")
             or "boucle_unique" in traits.get("accessoires", [])),
        joues(force=traits.get("joues", 0.2 if femme else 0.1)),
        rides(peau, traits.get("age", 30)),
        sourcils(expr.get("sourcils", "neutre"), assombrir(cheveux, 0.8) if traits.get("cheveux") not in ("blanc", "argent")
                 else "#8f8a84"),
        yeux(expr.get("yeux", "ouverts"), femme, expr.get("regard", 0.0)),
        nez(peau, traits.get("nez_rouge", False)),
        bouche(expr.get("bouche", "neutre"), traits.get("levres")),
        pilosite(traits.get("pilosite"), CHEVEUX.get(traits.get("pilosite_couleur", ""), cheveux)),
        cheveux_avant(coiffure, cheveux, traits.get("meche")),
        lunettes(traits.get("lunettes")),
        chapeau(traits.get("chapeau"), traits.get("chapeau_couleur", "#1b1612"), traits.get("ruban")),
        accessoires(traits.get("accessoires", []), v),
    ]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160" role="img" aria-label="{html.escape(nom)}">
<defs><clipPath id="medaillon"><circle cx="80" cy="80" r="72"/></clipPath></defs>
<g clip-path="url(#medaillon)">{contenu[0]}<g transform="translate(80 88) scale(1.14) translate(-80 -88)">{"".join(contenu[1:])}</g></g>
<circle cx="80" cy="80" r="74" fill="none" stroke="{OR}" stroke-width="5"/>
<circle cx="80" cy="80" r="69" fill="none" stroke="{OR}" stroke-width="1" stroke-dasharray="3 4" opacity="0.8"/>
</svg>"""


def data_uri(svg):
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def charger_traits(dossier_affaire):
    chemin = Path(dossier_affaire) / "portraits.json"
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


def planche(dossier_affaire, sortie=None):
    """Page HTML de contrôle : tous les portraits d'une affaire, en grand et en petit."""
    traits = charger_traits(dossier_affaire)
    noms = {}
    for f in (Path(dossier_affaire) / "characters").glob("*.json"):
        j = json.loads(f.read_text(encoding="utf-8"))
        noms[j["id"]] = (j["nom"], j["identite"])
    cartes = "".join(
        f'<figure><img src="{data_uri(dessiner(t, noms.get(i, (i, ""))[0]))}" width="220">'
        f'<img src="{data_uri(dessiner(t))}" width="44"><figcaption><b>{html.escape(noms.get(i, (i, ""))[0])}</b><br>'
        f'{html.escape(noms.get(i, ("", ""))[1])}</figcaption></figure>' for i, t in traits.items())
    page = (f'<!doctype html><meta charset="utf-8"><body style="background:#1b1612;color:#eadfc8;font-family:Georgia;'
            f'display:flex;flex-wrap:wrap;gap:24px;padding:24px">{cartes}</body>')
    sortie = Path(sortie or Path(tempfile.gettempdir()) / f"portraits_{Path(dossier_affaire).name}.html")
    sortie.write_text(page, encoding="utf-8")
    return sortie


if __name__ == "__main__":
    for d in sys.argv[1:] or ["cases/main_case", "cases/theatre_miroir"]:
        print(planche(d))
