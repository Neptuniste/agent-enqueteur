"""Interface ludique du jeu : lanceur des enquêtes, interrogatoires, pièces, carnet, accusation.

L'interface du rendu reste src/app.py ; celle-ci en est une version plus ludique, qui sait jouer
plusieurs affaires (tous les sous-dossiers de cases/ qui contiennent un case.json).
"""

from src.jeu.interface import creer_jeu, lancer_jeu

__all__ = ["creer_jeu", "lancer_jeu"]
