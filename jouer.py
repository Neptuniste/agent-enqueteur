"""Lanceur du jeu : choisir une enquête et jouer.

    python jouer.py --demo                 # sans modèle ni GPU : les personnages répondent avec leur fiche
    python jouer.py                        # le modèle (GPU) et son adaptateur LoRA (adapter/ ou ADAPTER_REPO)
    python jouer.py --sans-adaptateur      # le modèle de base seul : la baseline
    python jouer.py --petit                # petit modèle sur CPU, pour essayer (lent, réponses médiocres)
    python jouer.py --classique --affaire theatre_miroir   # l'interface du rendu (src/app.py)
    python jouer.py --share                # lien public temporaire, à partager

Par défaut, l'interface ludique (src/jeu/) propose toutes les affaires de cases/ et s'ouvre dans le navigateur.
"""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
PETIT_MODELE = "Qwen/Qwen2.5-0.5B-Instruct"


def adaptateur_par_defaut():
    from src.config import ADAPTER_REPO
    if (ROOT / "adapter" / "adapter_config.json").exists():
        return str(ROOT / "adapter")
    return ADAPTER_REPO or None


def main():
    parser = argparse.ArgumentParser(description="Les Dossiers de l'Inspecteur : lanceur du jeu")
    parser.add_argument("--demo", action="store_true", help="sans modèle : réponses tirées des fiches")
    parser.add_argument("--petit", action="store_true", help=f"{PETIT_MODELE} sur CPU, sans adaptateur")
    parser.add_argument("--modele", help="modèle de base (par défaut celui de src/config.py)")
    parser.add_argument("--adaptateur", help="dossier ou dépôt Hugging Face de l'adaptateur LoRA")
    parser.add_argument("--sans-adaptateur", action="store_true", help="modèle de base seul")
    parser.add_argument("--classique", action="store_true", help="interface du rendu au lieu de l'interface ludique")
    parser.add_argument("--affaire", default="main_case", help="avec --classique : le dossier de cases/ à jouer")
    parser.add_argument("--share", action="store_true", help="lien public temporaire")
    parser.add_argument("--port", type=int, default=None,
                        help="port local (par défaut le premier libre à partir de 7860)")
    parser.add_argument("--sans-navigateur", action="store_true", help="ne pas ouvrir le navigateur automatiquement")
    args = parser.parse_args()
    os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    model = tokenizer = generer = None
    if args.demo:
        from src.jeu.demo import generateur_demo
        generer, affiche = generateur_demo(), "mode démo"
    else:
        from src.config import MODEL_NAME
        from src.llm import charger_modele
        nom = PETIT_MODELE if args.petit else (args.modele or MODEL_NAME)
        adaptateur = None if (args.petit or args.sans_adaptateur) else (args.adaptateur or adaptateur_par_defaut())
        if adaptateur is None and not (args.petit or args.sans_adaptateur):
            print("ATTENTION : aucun adaptateur (ni adapter/, ni ADAPTER_REPO dans src/config.py) : modèle de base seul.")
        print(f"Chargement de {nom}" + (f" avec l'adaptateur {adaptateur}" if adaptateur else "") + "…")
        model, tokenizer = charger_modele(nom, adaptateur=adaptateur)
        affiche = nom.split("/")[-1] + (" + LoRA" if adaptateur else "")

    options = dict(share=args.share, server_port=args.port, inbrowser=not args.sans_navigateur)
    if args.classique:
        from src.app import lancer
        lancer(model, tokenizer, generer, modele_affiche=affiche, dossier=ROOT / "cases" / args.affaire, **options)
    else:
        from src.jeu import lancer_jeu
        lancer_jeu(model, tokenizer, generer, demo=args.demo, modele_affiche=affiche, **options)


if __name__ == "__main__":
    main()
