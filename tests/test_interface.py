"""Tests du jeu et de l'interface, sans modèle : un générateur factice remplace le LLM.

    python tests/test_interface.py

1. logique de Partie : secrets verrouillés, aveux, pièces débloquées, état rétabli après une panne,
   chaîne complète jusqu'aux 12 pièces, accusation ;
2. interface Gradio lancée en local et pilotée par gradio_client, comme un navigateur.
"""
import copy
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass
from src.app import AFFAIRE, QUESTION_PAR_DEFAUT, Partie, lancer, texte_pieces, texte_verdict
from src.game_state import charger_affaire

case, fiches = charger_affaire(AFFAIRE)
appels = []


def faux(systeme, historique, question, fiche, secrets_avoues, deja_connu):
    appels.append(dict(systeme=systeme, historique=historique, question=question, perso=fiche["id"],
                       avoues=secrets_avoues, connu=deja_connu))
    return f"*(Un temps.)* Réponse {len(appels)} de {fiche['nom']}."


secret = lambda perso, sid: next(s for s in fiches[perso]["secrets"] if s["id"] == sid)
doc = lambda pid: (AFFAIRE / next(x for x in case["pieces"] if x["id"] == pid)["document"]).read_text(encoding="utf-8")

# 1. question simple : secret verrouillé
p = Partie(case, fiches)
r, nv = p.tour("leon_perrin", "Bonsoir docteur.", faux)
flacon = secret("leon_perrin", "flacon")
assert nv == [] and "## Ce qui se passe maintenant" not in appels[-1]["systeme"]
assert flacon["verite"] not in appels[-1]["systeme"]
assert len(p.historiques["leon_perrin"]) == 2 and appels[-1]["historique"] == []

# 2. bonne pièce : aveu forcé, pièces débloquées, connu calculé avant le tour
r, nv = p.tour("leon_perrin", "", faux, piece="piece_flacon")
a = appels[-1]
assert a["question"] == "*(L'inspecteur vous montre le flacon vide.)* " + QUESTION_PAR_DEFAUT, a["question"]
assert "Cette pièce te force à avouer" in a["systeme"] and flacon["verite"] in a["systeme"]
assert "flacon" in a["avoues"]
assert set(nv) == {"piece_trousse", "piece_boucle_oreille"}, nv
assert a["historique"] == p.historiques["leon_perrin"][:2]
assert doc("piece_trousse")[:60] not in a["connu"] and doc("piece_flacon")[:60] in a["connu"]
assert "Bonsoir docteur." in a["connu"]

# 3. tour suivant : l'aveu passe dans « Ce que tu as déjà avoué »
p.tour("leon_perrin", "Continuez.", faux)
assert "## Ce que tu as déjà avoué" in appels[-1]["systeme"] and flacon["verite"] in appels[-1]["systeme"]
assert "## Ce qui se passe maintenant" not in appels[-1]["systeme"]

# 4. échec de génération : rien ne change
avant = copy.deepcopy((p.jeu.disponibles, p.jeu.montrees, p.jeu.avoues, p.historiques))
def panne(**_):
    raise RuntimeError("CUDA out of memory")
try:
    p.tour("josephine_laurent", "", panne, piece="piece_boucle_oreille")
    raise SystemExit("la panne aurait dû remonter")
except RuntimeError:
    pass
assert (p.jeu.disponibles, p.jeu.montrees, p.jeu.avoues, p.historiques) == avant

# 5. pièce sans rapport : aucun aveu, aucune pièce nouvelle
r, nv = p.tour("armand_riviere", "Et ça ?", faux, piece="piece_flacon")
assert nv == [] and "ne touche à aucun de tes secrets" in appels[-1]["systeme"]
assert p.jeu.avoues.get("armand_riviere", []) == []

# 6. réinitialiser : historique effacé, aveux gardés
p.reinitialiser("leon_perrin")
assert p.historiques["leon_perrin"] == [] and "flacon" in p.jeu.avoues["leon_perrin"]

# 7. chaîne complète : les 12 pièces sont accessibles, le meurtre n'est jamais dans un prompt
for perso, piece in [("josephine_laurent", "piece_boucle_oreille"), ("celeste_moreau", "piece_carnet_noir"),
                     ("rose_delorme", "piece_trousse"), ("rose_delorme", "piece_liasse_billets"),
                     ("rose_delorme", "piece_testament"), ("rose_delorme", "piece_deposition_josephine")]:
    p.tour(perso, "Expliquez-vous.", faux, piece=piece)
assert len(p.jeu.disponibles) == 12, p.jeu.disponibles
meurtre = secret("rose_delorme", "meurtre")
assert meurtre["verite"] == "" and all(case["solution"][:50] not in x["systeme"] for x in appels)
assert all(case["aveu_final"][:50] not in x["systeme"] for x in appels)
assert "### La trousse" in texte_pieces(p.jeu) or "### La trousse" in texte_pieces(p.jeu).replace("trousse noire", "trousse")

# 8. accusation
assert p.accuser("rose_delorme") is True and p.accuser("armand_riviere") is False
e, sol = texte_verdict(p.jeu, "rose_delorme", True)
assert "Affaire résolue" in e and case["aveu_final"] in sol and "12 sur" not in e
print(e.splitlines()[-1])
e, _ = texte_verdict(Partie(case, fiches).jeu, "armand_riviere", False)
assert "Erreur judiciaire" in e
print("Partie : 8 groupes de tests OK")

# 9. interface Gradio, pilotée comme un navigateur
from gradio_client import Client
texte_de = lambda m: m["content"] if isinstance(m["content"], str) else " ".join(x.get("text", "") for x in m["content"])
app, url, _ = lancer(generer=faux, share=False, prevent_thread_lock=True, quiet=True, server_port=7869)
c = Client(url, verbose=False)
noms = sorted(c.view_api(return_format="dict", print_info=False)["named_endpoints"])
print("points d'accès :", noms)
assert {"/afficher_interroger", "/afficher_presenter", "/interroger", "/presenter"} <= set(noms)
# la question s'affiche avant la réponse, sans appeler le modèle ni toucher à l'état du jeu
n = len(appels)
chat = c.predict("leon_perrin", "Bonsoir docteur.", api_name="/afficher_interroger")
assert len(chat) == 1 and chat[0]["role"] == "user" and texte_de(chat[0]) == "Bonsoir docteur.", chat
chat = c.predict("leon_perrin", "", "piece_flacon", api_name="/afficher_presenter")
assert texte_de(chat[-1]).startswith("*(L'inspecteur vous montre le flacon vide.)*"), chat
assert len(appels) == n, "l'affichage a appelé le modèle"
chat, q, piece, pieces_md, statut = c.predict("leon_perrin", "Bonsoir docteur.", api_name="/interroger")
assert len(chat) == 2 and q == "" and "Pièces à conviction (7)" in pieces_md, (chat, pieces_md[:60])
chat, q, piece, pieces_md, statut = c.predict("leon_perrin", "", "piece_flacon", api_name="/presenter")
assert "Nouvelle pièce" in statut and "Pièces à conviction (9)" in pieces_md, statut
print("format d'un message :", chat[-2])
texte = lambda m: m["content"] if isinstance(m["content"], str) else " ".join(x.get("text", "") for x in m["content"])
assert texte(chat[-2]).startswith("*(L'inspecteur vous montre le flacon vide.)*"), chat[-2]
assert chat[-1]["role"] == "assistant"
# une pièce débloquée en cours de partie doit être acceptée par la liste déroulante
chat, q, piece, pieces_md, statut = c.predict("rose_delorme", "Et ceci ?", "piece_trousse", api_name="/presenter")
assert "Nouvelle pièce" in statut, statut
print("Rose, trousse :", statut)
# l'affichage ne doit pas modifier les historiques du jeu (contenus restés des chaînes)
assert all(isinstance(m["content"], str) for x in appels for m in x["historique"]), appels[-1]["historique"]
c.predict("leon_perrin", "Encore une question.", api_name="/interroger")
assert len(appels[-1]["historique"]) == 4 and all(isinstance(m["content"], str) for m in appels[-1]["historique"])
assert "## Ce que tu as déjà avoué" in appels[-1]["systeme"]
valeur = lambda x: x.get("value") if isinstance(x, dict) and "__type__" in x else x
chat, identite, statut = c.predict("leon_perrin", api_name="/changer_personnage")
print("changement de personnage :", {k: (v if k != "value" else f"{len(v)} messages") for k, v in chat.items()} if isinstance(chat, dict) else len(chat))
chat = valeur(chat)
assert len(chat) == 6 and "Léon Perrin" in identite, (len(chat), identite)
chat, statut = c.predict("leon_perrin", api_name="/reinitialiser")
assert chat == [] and "reste acquis" in statut
verdict, solution = c.predict("armand_riviere", api_name="/accuser")
assert "Erreur judiciaire" in verdict and case["mobile"][:40] in solution
verdict, solution = c.predict("rose_delorme", api_name="/accuser")
assert "Affaire résolue" in verdict
sortie = c.predict("leon_perrin", api_name="/nouvelle_partie")
assert "Pièces à conviction (7)" in sortie[3] and sortie[0] == [], sortie[3][:40]
chat, *_ = c.predict("leon_perrin", api_name="/changer_personnage")
assert valeur(chat) == []
# une autre session (autre client) a sa propre partie
c2 = Client(url, verbose=False)
chat, *_ = c2.predict("leon_perrin", "Bonjour.", api_name="/interroger")
assert len(chat) == 2
print("Interface : OK")
