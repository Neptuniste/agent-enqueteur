"""Tests de l'interface ludique (src/jeu/), sans modèle : le mode démo remplace le LLM.

    python tests/test_jeu.py

1. moteur, sur les deux affaires : dossier public sans secret, chaîne d'aveux complète, refus,
   accusation fausse puis révélation, accusation juste et score, reprise d'une partie ;
2. si Playwright et Chrome (ou Edge) sont installés, parcours complet dans le navigateur :
   lanceur, une du journal, dossier lu avant de prendre l'affaire, portraits, interrogatoire, pièce montrée et pièce glissée, dossier, carnet, verdict.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

from src.jeu.demo import RIEN, generateur_demo, premiere_personne  # noqa: E402
from src.jeu.moteur import ErreurDeJeu, MoteurDeJeu  # noqa: E402

# --- 1. Moteur ---------------------------------------------------------------------------------
assert premiere_personne("Tu ne possèdes plus aucune arme.") == "Je ne possède plus aucune arme."
assert premiere_personne("Tu as vu ton frère ; il t'a parlé.") == "J'ai vu mon frère ; il m'a parlé."
assert premiere_personne("Ton frère : tu en parles.") == "Mon frère : j'en parle."
assert premiere_personne("C'est toi qui as tiré.") == "C'est moi qui ai tiré."

moteur = MoteurDeJeu(generateur_demo(), mode="demo")
ids = [a["id"] for a in moteur.catalogue()["affaires"]]
assert ids[0] == "faisan_dore" and "theatre_miroir" in ids, ids

for affaire in ids:
    case, fiches = moteur.affaire(affaire)
    r = moteur.ouvrir(affaire)
    public = json.dumps(r, ensure_ascii=False)
    secrets = [s["verite"][:40] for f in fiches.values() for s in f["secrets"] if s["verite"]]
    for interdit in [case["solution"][:50], case["aveu_final"][:50], "role_enquete", "mots_interdits", *secrets]:
        assert interdit not in public, (affaire, interdit)
    assert len(r["pieces"]) == sum(p["disponible_au_depart"] for p in case["pieces"])
print("dossiers publics sans secret :", ids)

# Mode démo : les questions que suggère l'interface (rendreSuggestions dans jeu.js) ont une réponse, et un
# nom de famille partagé ne fait pas répondre sur un autre personnage (« Rose Delorme » n'est pas Victor).
for affaire in ids:
    case, fiches = moteur.affaire(affaire)
    s = moteur.ouvrir(affaire)["session"]
    suggestions = ["Racontez-moi votre soirée.", "Où étiez-vous au moment du drame ?",
                   f"Que pensez-vous de {case['victime']['nom']} ?", "Avez-vous remarqué quelque chose d'inhabituel ?",
                   "Qui pouvait lui en vouloir ?"]
    for perso in fiches:
        for question in suggestions:
            assert moteur.interroger(s, perso, question)["reponse"] not in RIEN, (affaire, perso, question)
s = moteur.ouvrir("faisan_dore")["session"]
reponse = moteur.interroger(s, "celeste_moreau", "Que pensez-vous de Rose Delorme ?")["reponse"]
assert not reponse.startswith("Victor"), reponse
assert "Lili" in moteur.interroger(s, "celeste_moreau", "", "piece_carnet_noir")["reponse"]
assert "sais pas qui" in moteur.interroger(s, "celeste_moreau", "Qui a tué Victor ?")["reponse"]

r = moteur.ouvrir("theatre_miroir")
s = r["session"]
etapes = [("firmin_lagarde", "piece_ardoise"), ("adele_brissac", "piece_ruban"), ("basile_roux", "piece_deposition_adele"),
          ("colette_valrose", "piece_programme"), ("edmond_sorel", "piece_manuscrit")]
for perso, piece in etapes:
    q = moteur.interroger(s, perso, "Expliquez-vous.", piece)
    assert q["aveu"], (perso, piece, q["reponse"])
assert q["progression"]["pieces"] == 11 and len(moteur.sessions[s].carnet) == 5
q = moteur.interroger(s, "edmond_sorel", "Et ceci ?", "piece_cartouche_blanc")
assert not q["aveu"]
for args in [(s, "personne", "x"), ("inconnue", "edmond_sorel", "x"), (s, "edmond_sorel", "", None)]:
    try:
        moteur.interroger(*args)
        raise AssertionError(f"aurait dû être refusé : {args}")
    except ErreurDeJeu:
        pass
v = moteur.accuser(s, "raoul_despreaux")
assert not v["juste"] and "solution" not in v and v["score"] <= 40
v = moteur.reveler(s)
assert v["coupable"] == "Edmond Sorel" and v["solution"]
try:
    moteur.interroger(s, "edmond_sorel", "Encore ?")
    raise AssertionError("la partie aurait dû être close")
except ErreurDeJeu:
    pass
assert moteur.reprendre(s)["verdict"]["revele"]

r = moteur.ouvrir("theatre_miroir")
v = moteur.accuser(r["session"], "edmond_sorel", {"mobile": "piece_programme", "moyen": "piece_douille",
                                                  "opportunite": "piece_ardoise"})
assert v["juste"] and v["grade"] == "Inspecteur", v  # au flair, sans enquête : pas le grade suprême
print("moteur : OK")

# --- 2. Navigateur (facultatif) -----------------------------------------------------------------
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("navigateur : sauté (pip install playwright pour l'activer)")
    sys.exit(0)

from src.jeu.interface import CSS_PAGE, creer_jeu  # noqa: E402

page_gradio, _ = creer_jeu(demo=True)
_, url, _ = page_gradio.launch(prevent_thread_lock=True, quiet=True, server_port=7877, css=CSS_PAGE)
erreurs, captures = [], Path(tempfile.mkdtemp(prefix="jeu_"))
with sync_playwright() as p:
    navigateur = None
    for canal in ("chrome", "msedge", None):
        try:
            navigateur = p.chromium.launch(channel=canal, headless=True) if canal else p.chromium.launch(headless=True)
            break
        except Exception:
            continue
    if navigateur is None:
        print("navigateur : sauté (ni Chrome, ni Edge, ni Chromium de Playwright)")
        sys.exit(0)
    page = navigateur.new_page(viewport={"width": 1366, "height": 860})
    page.on("pageerror", lambda e: erreurs.append(str(e)))
    page.on("console", lambda m: erreurs.append(m.text) if m.type == "error" else None)
    attendre_fin = "!document.querySelector('.jx-saisie input').disabled"

    page.goto(url)
    page.wait_for_selector(".jx-affiche", timeout=30000)
    assert page.locator(".jx-affiche").count() == len(ids)
    page.locator(".jx-affiche").nth(1).locator("button").click()
    page.wait_for_selector(".jx-journal")          # la une d'abord, sans fenêtre par-dessus
    assert page.locator(".jx-fenetre").count() == 0
    boutons = page.locator(".jx-journal .jx-actions button")
    assert boutons.all_text_contents()[:2] == ["Lire le dossier", "Prendre l'affaire"], boutons.all_text_contents()
    assert boutons.nth(1).is_disabled(), "l'affaire ne se prend qu'après le dossier"
    boutons.nth(0).click()
    page.wait_for_selector(".jx-fenetre")
    assert page.locator(".jx-fenetre header h2").inner_text() == "Le dossier"
    fen = page.locator(".jx-fenetre").bounding_box()
    page.locator(".jx-corps").evaluate("e => e.scrollTop = e.scrollHeight")
    fin = page.locator(".jx-corps .jx-document > *").last.bounding_box()
    assert fen["y"] >= 0 and fin["y"] + fin["height"] <= fen["y"] + fen["height"] <= page.viewport_size["height"], (fen, fin)
    page.keyboard.press("Escape")
    assert page.locator(".jx-fenetre").count() == 0 and boutons.nth(1).is_enabled()
    assert boutons.nth(0).text_content() == "Relire le dossier"
    boutons.nth(1).click()
    page.wait_for_selector(".jx-suspect")
    portraits = page.locator(".jx-suspect img").evaluate_all("l => l.map(i => i.src)")
    assert len(set(portraits)) == len(portraits) == 7, "un portrait distinct par personnage"
    page.locator(".jx-suspect", has_text="Firmin Lagarde").click()
    page.fill(".jx-saisie input", "Où étiez-vous pendant l'entracte ?")
    page.keyboard.press("Enter")
    page.wait_for_selector(".jx-replique.jx-perso .jx-texte:not(.jx-reflexion)", timeout=20000)
    page.locator(".jx-dialogue").click()
    page.wait_for_function(attendre_fin, timeout=20000)
    page.locator(".jx-piece", has_text="L'ardoise du bistro").get_by_text("Montrer").click()
    page.wait_for_selector(".jx-piece.jx-nouvelle", timeout=20000)
    page.locator(".jx-dialogue").click()
    page.wait_for_function(attendre_fin, timeout=20000)
    page.locator(".jx-suspect", has_text="Adèle Brissac").click()
    page.locator(".jx-piece", has_text="ruban").drag_to(page.locator(".jx-interrogatoire"))
    page.wait_for_function("document.querySelectorAll('.jx-piece').length === 9", timeout=20000)
    page.locator(".jx-dialogue").click()
    page.wait_for_function(attendre_fin, timeout=20000)
    page.get_by_role("button", name="Carnet").click()
    page.wait_for_selector(".jx-carnet-entree")
    assert page.locator(".jx-carnet-entree").count() == 2
    page.keyboard.press("Escape")
    page.get_by_role("button", name="Accuser").click()
    page.locator(".jx-choix", has_text="Edmond Sorel").click()
    page.get_by_text("J'accuse !").click()
    page.wait_for_selector(".jx-tampon.jx-ok")
    page.wait_for_timeout(700)
    page.screenshot(path=str(captures / "verdict.png"))
    navigateur.close()
page_gradio.close()
assert not erreurs, erreurs
print(f"navigateur : OK (capture du verdict : {captures / 'verdict.png'})")
