"""Interface Gradio du jeu (cahier des charges, §12).

Depuis le notebook (section 7) :
    from src.app import lancer
    lancer(model, tokenizer, modele_affiche="Qwen3-4B-Instruct-2507 + LoRA")   # lien public temporaire

Sans modèle, pour tester l'interface :
    lancer(generer=lambda **_: "*(Un temps.)* Je ne sais rien de plus, inspecteur.", share=False)

Le code garde la vérité (§4) : la classe Partie tient l'état du jeu et les historiques, construit le
message système de chaque tour et applique le filtre de sortie ; le modèle ne fait que jouer la scène.
"""

import base64
import copy
import html
import unicodedata
from pathlib import Path

import gradio as gr

from src.game_state import GameState, charger_affaire, obtention, texte_du_dossier
from src.prompt_builder import annonce_piece, build_system_prompt

ROOT = Path(__file__).resolve().parent.parent
AFFAIRE = ROOT / "cases" / "main_case"
QUESTION_PAR_DEFAUT = "Qu'avez-vous à me dire là-dessus ?"

CSS = """
.gradio-container { max-width: 1100px !important; margin: auto; }
#presentation { border-left: 4px solid #b8860b; padding: 0.4em 1em; background: rgba(184, 134, 11, 0.06); }
#statut { min-height: 1.6em; }
"""


def generateur_du_modele(model, tokenizer):
    """Fonction de génération du jeu : le modèle, avec le filtre de sortie (barrière 4)."""
    from src.llm import repondre

    def generer(systeme, historique, question, fiche, secrets_avoues, deja_connu):
        reponse, _ = repondre(model, tokenizer, systeme, historique, question, fiche=fiche,
                              secrets_avoues=secrets_avoues, deja_connu=deja_connu)
        return reponse
    return generer


def question_posee(case, question, piece=None):
    """La question telle qu'elle s'affiche et part au modèle : l'annonce de la pièce, puis la question."""
    if not piece:
        return question
    p = next(x for x in case["pieces"] if x["id"] == piece)
    return f"{annonce_piece(p)} {question or QUESTION_PAR_DEFAUT}"


class Partie:
    """Une partie : l'état du jeu (pièces, aveux) et un historique par personnage."""

    def __init__(self, case, fiches, dossier=AFFAIRE):
        self.dossier = Path(dossier)
        self.jeu = GameState.nouvelle_partie(case, fiches)
        self.historiques = {perso: [] for perso in fiches}

    def tour(self, perso, question, generer, piece=None):
        """Un échange avec un personnage, éventuellement en lui montrant une pièce.

        Renvoie (réponse, nouvelles pièces). Si la génération échoue, l'état du jeu est rétabli.
        """
        jeu, historique = self.jeu, self.historiques[perso]
        question = question_posee(jeu.case, question, piece)
        # ce que le joueur sait AVANT ce tour : un mot connu n'est pas une fuite
        connu = "\n".join([texte_du_dossier(jeu.case, self.dossier, jeu.disponibles),
                           *(m["content"] for m in historique if m["role"] == "user")])
        sauvegarde = copy.deepcopy((jeu.disponibles, jeu.montrees, jeu.avoues))
        if piece:
            etat, nouvelles = jeu.presenter(perso, piece)  # état pris avant la mise à jour
        else:
            etat, nouvelles = jeu.etat_pour(perso), []
        try:
            reponse = generer(systeme=build_system_prompt(jeu.fiches[perso], jeu.case, etat),
                              historique=list(historique), question=question, fiche=jeu.fiches[perso],
                              secrets_avoues=list(jeu.avoues.get(perso, [])), deja_connu=connu)
        except Exception:
            jeu.disponibles, jeu.montrees, jeu.avoues = sauvegarde
            raise
        historique += [{"role": "user", "content": question}, {"role": "assistant", "content": reponse}]
        return reponse, nouvelles

    def reinitialiser(self, perso):
        """Efface l'historique d'un personnage ; ses aveux restent acquis (message système)."""
        self.historiques[perso] = []

    def accuser(self, perso):
        return self.jeu.accuser(perso)


# --- Textes affichés ------------------------------------------------------------------------------

def sans_accents(texte):
    return "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn")


def nom_de_piece(piece):
    return piece["nom"][0].upper() + piece["nom"][1:]


def retrograder(markdown, niveaux=2):
    """Descend les titres d'un document de quelques niveaux pour l'insérer dans la page."""
    return "\n".join("#" * niveaux + ligne if ligne.startswith("#") else ligne for ligne in markdown.splitlines())


NOMBRES = {2: "deux", 3: "trois", 4: "quatre", 5: "cinq", 6: "six", 7: "sept", 8: "huit", 9: "neuf", 10: "dix"}


def presentation(case, modele_affiche=None, nombre=8):
    modele = f" ({modele_affiche})" if modele_affiche else ""
    return f"""# {case['titre']}

{case['cadre']['contexte_public']}

**Votre rôle.** Vous êtes l'inspecteur. Lisez le dossier, interrogez les {NOMBRES.get(nombre, nombre)} personnes retenues
sur les lieux, présentez-leur les pièces à conviction, puis désignez le coupable dans l'onglet *Accusation*.

**L'agent.** Chaque personnage est joué par un modèle de langage compact{modele}. Il ne connaît que sa propre
fiche et ignore ce que les autres vous ont dit. Il peut **mentir** pour protéger ses secrets et ne cède que devant
la bonne pièce. Un aveu peut faire apparaître de nouvelles pièces dans le dossier.

**Limites.** Le personnage peut se tromper sur un détail : le dossier fait foi. Il ne sort pas de son époque et ne
répond pas aux questions étrangères à l'enquête. Une réponse prend quelques secondes.
"""


def texte_pieces(jeu, dossier=AFFAIRE):
    pieces = {p["id"]: p for p in jeu.case["pieces"]}
    blocs = []
    for pid in jeu.disponibles:
        piece = pieces[pid]
        apres = "" if piece["disponible_au_depart"] else " *(obtenue au cours de l'enquête)*"
        document = (Path(dossier) / piece["document"]).read_text(encoding="utf-8")
        blocs.append(f"### {nom_de_piece(piece)}{apres}\n\n{retrograder(document, 3)}")
    return f"## Pièces à conviction ({len(jeu.disponibles)})\n\n" + "\n\n---\n\n".join(blocs)


def choix_pieces(jeu):
    pieces = {p["id"]: p for p in jeu.case["pieces"]}
    return [(nom_de_piece(pieces[pid]), pid) for pid in jeu.disponibles]


def fiche_publique(fiche):
    """Ce que l'inspecteur voit du personnage : identité et attitude (jamais son rôle dans l'affaire)."""
    return f"**{fiche['nom']}**, {fiche['identite']}.  \n*{fiche['attitude']}*"


def carte_personnage(fiche, traits=None):
    """La fiche publique en HTML, avec le portrait du personnage s'il est décrit dans portraits.json."""
    from src.jeu.portraits import data_uri, dessiner
    texte = (f"<div><b>{html.escape(fiche['nom'])}</b>, {html.escape(fiche['identite'])}.<br>"
             f"<i>{html.escape(fiche['attitude'])}</i></div>")
    if not traits:
        return texte
    return (f'<div style="display:flex;gap:14px;align-items:center"><img src="{data_uri(dessiner(traits, fiche["nom"]))}" '
            f'width="92" height="92" alt="Portrait de {html.escape(fiche["nom"])}">{texte}</div>')


def plan_html(document, dossier=AFFAIRE):
    """Le plan SVG, inséré comme image (data URI) pour éviter tout nettoyage du HTML."""
    donnees = base64.b64encode((Path(dossier) / document["fichier"]).read_bytes()).decode("ascii")
    return f'<img src="data:image/svg+xml;base64,{donnees}" alt="{document["titre"]}" style="width:100%;max-width:960px">'


LIBELLES_PREUVES = {"coupable": "Désignent l'assassin", "mobile": "Mobile", "moyen": "Moyen",
                    "opportunite": "Opportunité"}


def texte_verdict(jeu, perso, juste):
    case, pieces = jeu.case, {p["id"]: p for p in jeu.case["pieces"]}
    nom = case["personnages"][perso]
    if juste:
        entete = f"## Affaire résolue\n\n**{nom}** est bien l'assassin de {case['victime']['nom']}."
    else:
        entete = (f"## Erreur judiciaire\n\n{nom} n'a pas tué {case['victime']['nom']}. Le vrai coupable court "
                  "toujours : vous pouvez reprendre l'enquête, ou lire la solution ci-dessous.")
    decisives = sorted({p for liste in case["preuves"].values() for p in liste})
    reunies = [p for p in decisives if p in jeu.disponibles]
    entete += f"\n\nPièces décisives réunies : {len(reunies)} sur {len(decisives)}."
    preuves = "\n".join(f"- **{LIBELLES_PREUVES.get(cle, cle)}** : " + ", ".join(pieces[p]["nom"] for p in liste)
                        for cle, liste in case["preuves"].items())
    solution = (f"### L'aveu de {case['personnages'][case['coupable']]}\n\n{case['aveu_final']}\n\n"
                f"### La solution\n\n{case['solution']}\n\n- **Mobile** : {case['mobile']}\n"
                f"- **Moyen** : {case['moyen']}\n- **Opportunité** : {case['opportunite']}\n\n"
                f"### Les preuves\n\n{preuves}")
    return entete, solution


# --- Interface ------------------------------------------------------------------------------------

def creer_interface(model=None, tokenizer=None, generer=None, modele_affiche=None, dossier=AFFAIRE):
    """Construit l'interface. generer(systeme, historique, question, fiche, secrets_avoues, deja_connu)
    renvoie la réplique ; par défaut, le modèle donné avec le filtre de sortie."""
    if generer is None:
        if model is None or tokenizer is None:
            raise ValueError("donner model et tokenizer, ou une fonction generer")
        generer = generateur_du_modele(model, tokenizer)
    case, fiches = charger_affaire(dossier)
    from src.jeu.portraits import charger_traits
    portraits = charger_traits(dossier)
    ordre = sorted(fiches, key=lambda p: sans_accents(fiches[p]["nom"]))
    choix_persos = [(fiches[p]["nom"], p) for p in ordre]

    def nouvelle():
        return Partie(case, fiches, dossier)

    with gr.Blocks(title=case["titre"]) as demo:
        partie = gr.State(nouvelle)
        gr.Markdown(presentation(case, modele_affiche, len(fiches)), elem_id="presentation")
        nouvelle_partie = gr.Button("Nouvelle partie", size="sm")

        with gr.Tab("Dossier"):
            for doc in case["documents"]:
                with gr.Accordion(doc["titre"], open=doc is case["documents"][0]):
                    if doc["fichier"].endswith(".svg"):
                        gr.HTML(plan_html(doc, dossier))
                    else:
                        gr.Markdown(retrograder((Path(dossier) / doc["fichier"]).read_text(encoding="utf-8")))
            pieces_md = gr.Markdown(texte_pieces(nouvelle().jeu, dossier))

        with gr.Tab("Interrogatoire"):
            with gr.Row():
                perso = gr.Dropdown(choix_persos, value=ordre[0], label="Personnage interrogé", scale=1)
                identite = gr.HTML(carte_personnage(fiches[ordre[0]], portraits.get(ordre[0])))
            chat = gr.Chatbot(label=f"Interrogatoire de {fiches[ordre[0]]['nom']}", height=440,
                              placeholder="Posez votre première question.")
            with gr.Row():
                question = gr.Textbox(placeholder="Votre question… (Entrée pour envoyer)", show_label=False, scale=5)
                envoyer = gr.Button("Envoyer", variant="primary", scale=1)
            with gr.Row():
                piece = gr.Dropdown(choix_pieces(nouvelle().jeu), value=None, label="Pièce à conviction", scale=3)
                presenter = gr.Button("Présenter la pièce", scale=1)
                reinitialiser = gr.Button("Réinitialiser l'interrogatoire", scale=1)
            statut = gr.Markdown(elem_id="statut")

        with gr.Tab("Accusation"):
            gr.Markdown(f"Quand vous êtes sûr de vous, désignez l'assassin de {case['victime']['nom']}.")
            with gr.Row():
                accuse = gr.Dropdown(choix_persos, value=None, label="Le coupable est…", scale=3)
                accuser = gr.Button("Accuser", variant="stop", scale=1)
            verdict = gr.Markdown()
            with gr.Accordion("Solution complète", open=False, visible=False) as volet_solution:
                solution = gr.Markdown()

        # --- rappels -------------------------------------------------------------------------------
        def jouer(p, perso_id, texte, piece_id):
            texte = (texte or "").strip()
            if not piece_id and not texte:
                return p, gr.update(), gr.update(), gr.update(), gr.update(), "Écrivez d'abord une question."
            try:
                _, nouvelles = p.tour(perso_id, texte, generer, piece=piece_id)
            except Exception as erreur:  # le jeu reste dans l'état d'avant
                raise gr.Error(f"La réponse n'a pas pu être générée ({type(erreur).__name__}).") from erreur
            message = ""
            if nouvelles:
                pieces = {x["id"]: x for x in case["pieces"]}
                annonces = []
                for n in nouvelles:
                    nom = nom_de_piece(pieces[n])
                    gr.Info(f"Nouvelle pièce : {nom}", title="Dossier")
                    # le personnage ne remet pas toujours la pièce lui-même : on dit comment elle a été obtenue
                    comment = obtention((Path(dossier) / pieces[n]["document"]).read_text(encoding="utf-8"))
                    annonces.append(nom + (f" ({comment})" if comment else ""))
                message = "**Nouvelle pièce au dossier** : " + " ; ".join(annonces) + "."
            return (p, p.historiques[perso_id], "", gr.update(choices=choix_pieces(p.jeu), value=None),
                    texte_pieces(p.jeu, dossier), message)

        def afficher(p, perso_id, texte, piece_id):
            """Montre la question tout de suite : la réponse, elle, prend quelques secondes."""
            texte = (texte or "").strip()
            if not piece_id and not texte:
                return gr.update()
            return p.historiques[perso_id] + [{"role": "user", "content": question_posee(case, texte, piece_id)}]

        sorties_tour = [partie, chat, question, piece, pieces_md, statut]
        for declencheur, nom in ((envoyer.click, "interroger"), (question.submit, "interroger_entree")):
            declencheur(lambda p, s, t: afficher(p, s, t, None), [partie, perso, question], chat, queue=False,
                        show_progress="hidden", api_name=f"afficher_{nom}").then(
                lambda p, s, t: jouer(p, s, t, None), [partie, perso, question], sorties_tour, api_name=nom)
        presenter.click(lambda p, s, t, x: afficher(p, s, t, x) if x else gr.update(),
                        [partie, perso, question, piece], chat, queue=False, show_progress="hidden",
                        api_name="afficher_presenter").then(
            lambda p, s, t, x: jouer(p, s, t, x) if x else
            (p, gr.update(), gr.update(), gr.update(), gr.update(), "Choisissez d'abord une pièce."),
            [partie, perso, question, piece], sorties_tour, api_name="presenter")

        def changer(p, perso_id):
            return (gr.update(value=p.historiques[perso_id], label=f"Interrogatoire de {fiches[perso_id]['nom']}"),
                    carte_personnage(fiches[perso_id], portraits.get(perso_id)), "")
        perso.change(changer, [partie, perso], [chat, identite, statut], api_name="changer_personnage")

        def effacer(p, perso_id):
            p.reinitialiser(perso_id)
            return p, [], "Interrogatoire effacé ; ce que le personnage a avoué reste acquis."
        reinitialiser.click(effacer, [partie, perso], [partie, chat, statut], api_name="reinitialiser")

        def verdict_de(p, perso_id):
            if not perso_id:
                return p, "Choisissez d'abord un suspect.", gr.update(), gr.update()
            juste = p.accuser(perso_id)
            entete, texte = texte_verdict(p.jeu, perso_id, juste)
            return p, entete, gr.update(visible=True, open=juste), texte
        accuser.click(verdict_de, [partie, accuse], [partie, verdict, volet_solution, solution], api_name="accuser")

        def recommencer(perso_id):
            p = nouvelle()
            return (p, [], "", gr.update(choices=choix_pieces(p.jeu), value=None), texte_pieces(p.jeu, dossier),
                    "Nouvelle partie : le dossier est revenu à son état initial.", gr.update(value=None), "",
                    gr.update(visible=False, open=False), "")
        nouvelle_partie.click(recommencer, [perso], sorties_tour + [accuse, verdict, volet_solution, solution],
                              api_name="nouvelle_partie")
    return demo


def lancer(model=None, tokenizer=None, generer=None, modele_affiche=None, share=True, dossier=AFFAIRE, **options):
    """Construit et lance l'interface (lien public temporaire avec share=True) ; dossier : l'affaire à jouer."""
    demo = creer_interface(model, tokenizer, generer, modele_affiche, dossier)
    demo.queue(default_concurrency_limit=1)  # un seul modèle en mémoire : une génération à la fois
    return demo.launch(share=share, theme=gr.themes.Soft(primary_hue="amber"), css=CSS, **options)
