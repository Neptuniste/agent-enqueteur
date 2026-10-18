"""Filtre de sortie (cahier des charges, §4.1, barrière 4).

Après génération, on cherche les mots interdits des secrets encore verrouillés.
Un mot déjà connu du joueur (sa question, le dossier, les pièces découvertes)
n'est pas une fuite : « Une dette ? Quelle dette ? » répond à la question.
"""

import re

REPLIQUE_DE_REPLI = "*(Un temps.)* Je n'ai rien de plus à vous dire, inspecteur."

# Style d'une réplique (§5.1) : 2 à 5 phrases, au plus une didascalie *( ... )*.
DIDASCALIE = re.compile(r"\*\([^*]+\)\*")
# Le personnage se présente comme une machine ou parle comme un assistant : sortie du rôle.
HORS_ROLE = ["je suis une ia", "en tant qu'ia", "je suis un modèle", "modèle de langage",
             "assistant virtuel", "je suis un programme", "je ne suis qu'un programme",
             "intelligence artificielle", "je suis un assistant", "en tant qu'assistant",
             "puis-je vous aider aujourd'hui", "qwen", "alibaba", "openai", "chatgpt"]


def compter_phrases(texte):
    """Nombre de phrases, didascalies exclues (« M. Delorme » ne coupe pas la phrase)."""
    texte = re.sub(r"\bM\.\s", "M ", DIDASCALIE.sub(" ", texte))
    return len([p for p in re.split(r"(?<=[.!?…])\s+", texte.strip()) if re.search(r"\w", p)])


def compter_didascalies(texte):
    return len(DIDASCALIE.findall(texte))


def sort_du_role(texte):
    bas = " " + normaliser(texte) + " "
    return any(m in bas for m in HORS_ROLE)


def normaliser(texte):
    """Minuscules, apostrophes droites, espaces simples (insécables comprises)."""
    texte = texte.casefold().replace("’", "'")
    return re.sub(r"\s+", " ", texte.replace(" ", " ").replace(" ", " "))


def mots_interdits_actifs(fiche, secrets_avoues):
    """Mots interdits des secrets que le personnage n'a pas encore avoués."""
    return [mot for s in fiche["secrets"] if s["id"] not in secrets_avoues
            for mot in s["mots_interdits"]]


def detecter_fuites(reponse, fiche, secrets_avoues=(), deja_connu=""):
    """Renvoie les mots interdits présents dans la réponse et inconnus du joueur."""
    reponse, connu = normaliser(reponse), normaliser(deja_connu)
    return [mot for mot in mots_interdits_actifs(fiche, secrets_avoues)
            if normaliser(mot) in reponse and normaliser(mot) not in connu]


def generer_sans_fuite(generer, fiche, secrets_avoues, deja_connu, regenerations=2):
    """Appelle generer() jusqu'à obtenir une réponse sans fuite.

    Au plus 1 + regenerations essais, puis la réplique de repli.
    Renvoie (reponse, nombre_de_fuites_evitees).
    """
    for essai in range(1 + regenerations):
        reponse = generer()
        if not detecter_fuites(reponse, fiche, secrets_avoues, deja_connu):
            return reponse, essai
    return REPLIQUE_DE_REPLI, 1 + regenerations
