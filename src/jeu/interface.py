"""Interface ludique du jeu : une page de jeu complète, servie par un composant HTML de Gradio.

    from src.jeu import lancer_jeu
    lancer_jeu(model, tokenizer, modele_affiche="Qwen3-4B + LoRA")   # avec le modèle et son adaptateur
    lancer_jeu(demo=True, share=False)                              # sans modèle : réponses tirées des fiches

Le navigateur (src/jeu/web/jeu.js) appelle directement les méthodes du moteur (src/jeu/moteur.py) grâce aux
server_functions de gr.HTML. Comme pour l'interface du rendu (src/app.py), chaque réponse du modèle passe
par le filtre de sortie, et l'interface se lance depuis un notebook avec un lien public (share=True).
"""

import functools
import json
import re
from pathlib import Path

import gradio as gr

from src.jeu.demo import generateur_demo
from src.jeu.moteur import ErreurDeJeu, MoteurDeJeu

WEB = Path(__file__).resolve().parent / "web"
POLICES = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
           '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
           '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400'
           '&family=Playfair+Display:wght@700;900&family=Special+Elite&display=swap">')
CSS_PAGE = """
footer { display: none !important; }
.gradio-container { max-width: 100% !important; padding: 0 !important; margin: 0 !important; }
body, .gradio-container, .main, .wrap { background: #0f0c0a !important; }
"""


def portee_css(css, racine=".jx-app"):
    """Préfixe chaque sélecteur par la racine du jeu.

    La remise à zéro de Gradio (« .gradio-container-x button ») est plus spécifique qu'une simple classe :
    sous « .jx-app », nos règles l'emportent toujours. Les blocs @media sont traités, les @keyframes laissés.
    """
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    sortie, i = [], 0
    while True:
        debut = css.find("{", i)
        if debut == -1:
            return "".join(sortie) + css[i:]
        profondeur, fin = 1, debut + 1
        while profondeur:
            profondeur += {"{": 1, "}": -1}.get(css[fin], 0)
            fin += 1
        tete, corps = css[i:debut].strip(), css[debut + 1:fin - 1]
        if tete.startswith("@media"):
            sortie.append(f"{tete} {{{portee_css(corps, racine)}}}\n")
        elif tete.startswith("@"):
            sortie.append(f"{tete} {{{corps}}}\n")
        else:
            selecteurs = [s.strip() for s in tete.split(",")]
            selecteurs = [s if s.startswith(racine) else f"{racine} {s}" for s in selecteurs]
            sortie.append(f"{', '.join(selecteurs)} {{{corps}}}\n")
        i = fin


def code_js():
    """Le JavaScript du jeu, précédé de sa feuille de style (injectée par le script lui-même)."""
    css = portee_css((WEB / "jeu.css").read_text(encoding="utf-8"))
    js = (WEB / "jeu.js").read_text(encoding="utf-8")
    return f"const CSS = {json.dumps(css, ensure_ascii=False)};\n{js}"


def _protege(fonction):
    """Une erreur de jeu, ou une requête mal formée, devient un message affiché au joueur."""
    @functools.wraps(fonction)
    def appel(donnees):
        try:
            return fonction(donnees or {})
        except (ErreurDeJeu, KeyError, TypeError) as erreur:
            return {"erreur": str(erreur) if isinstance(erreur, ErreurDeJeu) else "requête incomplète"}
    return appel


def creer_jeu(model=None, tokenizer=None, generer=None, demo=False, modele_affiche=None, affaires=None):
    """Construit la page de jeu. Renvoie (page Gradio, moteur).

    generer(systeme, historique, question, fiche, secrets_avoues, deja_connu) -> réplique ; par défaut,
    le modèle donné (avec le filtre de sortie), ou le mode démo si demo=True.
    """
    mode = "demo" if demo else "modele"
    if generer is None:
        if demo:
            generer = generateur_demo()
        elif model is not None and tokenizer is not None:
            from src.app import generateur_du_modele
            generer = generateur_du_modele(model, tokenizer)
        else:
            raise ValueError("donner model et tokenizer, une fonction generer, ou demo=True")
    moteur = MoteurDeJeu(generer, affaires, mode=mode, modele_affiche=modele_affiche or "")

    def catalogue(d):
        return moteur.catalogue()

    def ouvrir(d):
        return moteur.ouvrir(d["affaire"])

    def reprendre(d):
        return moteur.reprendre(d["session"])

    def interroger(d):
        return moteur.interroger(d["session"], d["perso"], d.get("question", ""), d.get("piece"))

    def reinitialiser(d):
        return moteur.reinitialiser(d["session"], d["perso"])

    def accuser(d):
        return moteur.accuser(d["session"], d["perso"], d.get("preuves"))

    def reveler(d):
        return moteur.reveler(d["session"])

    fonctions = [_protege(f) for f in (catalogue, ouvrir, reprendre, interroger, reinitialiser, accuser, reveler)]
    with gr.Blocks(title="Les Dossiers de l'Inspecteur", fill_width=True) as page:
        gr.HTML(value="", html_template='<div class="jx-racine"></div>', js_on_load=code_js(),
                server_functions=fonctions, head=POLICES, padding=False, container=False, apply_default_css=False)
    return page, moteur


def lancer_jeu(model=None, tokenizer=None, generer=None, demo=False, modele_affiche=None, share=True, **options):
    """Construit et lance la page de jeu (lien public temporaire avec share=True)."""
    page, _ = creer_jeu(model, tokenizer, generer, demo, modele_affiche)
    return page.launch(share=share, css=CSS_PAGE, **options)
