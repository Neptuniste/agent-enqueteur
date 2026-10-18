"""Mode démo : des réponses sans modèle de langage, tirées du message système du personnage.

Il sert à essayer l'interface et à tester une affaire sans GPU. Le personnage répond à la première
personne avec ce que contient son prompt : sa version officielle sur les sujets sensibles, ce qu'il sait,
son opinion sur les autres, et ses aveux quand on lui montre la bonne pièce. Comme le prompt ne contient
jamais un secret verrouillé (barrières 2 et 3), le mode démo ne peut rien divulguer.
"""

import random
import re

STOPWORDS = set("""avec dans pour pendant cette votre vous nous elle elles ils mais donc comme quand quoi
quel quelle quels quelles avez aviez était étiez êtes sont tout tous toute toutes alors aussi encore
leur leurs chez être avoir fait faire plus moins très bien vers sans sous sur entre depuis jamais rien
monsieur madame mademoiselle inspecteur soir soirée""".split())

AVEU = ["Un long silence.", "Il baisse les yeux.", "La voix se brise.", "Un temps.", "Il se tait, puis cède."]
NEUTRE = ["Il hausse les épaules.", "Un regard étonné.", "Un temps.", "Il fronce les sourcils."]
RIEN = ["Je n'en sais rien, inspecteur.", "Là, vous m'en demandez trop : je n'en sais rien.",
        "Je ne saurais vous dire, inspecteur."]

# Deuxième personne de la fiche -> première personne de la réplique (approximatif, mais lisible).
REMPLACEMENTS = [
    (r"\bTu n'as\b", "Je n'ai"), (r"\btu n'as\b", "je n'ai"), (r"\bTu n'es\b", "Je ne suis"),
    (r"\btu n'es\b", "je ne suis"), (r"\bTu t'es\b", "Je me suis"), (r"\btu t'es\b", "je me suis"),
    (r"\bTu as\b", "J'ai"), (r"\btu as\b", "j'ai"), (r"\bTu es\b", "Je suis"), (r"\btu es\b", "je suis"),
    (r"\bTu l'as\b", "Je l'ai"), (r"\btu l'as\b", "je l'ai"), (r"\bTu vas\b", "Je vais"), (r"\btu vas\b", "je vais"),
    (r"\bt'", "m'"), (r"\bte\b", "me"), (r"\btoi\b", "moi"), (r"\bTon\b", "Mon"), (r"\bton\b", "mon"),
    (r"\bTa\b", "Ma"), (r"\bta\b", "ma"), (r"\bTes\b", "Mes"), (r"\btes\b", "mes"),
    (r"\bTu\b", "Je"), (r"\btu\b", "je"),
]


def premiere_personne(texte):
    for motif, remplacement in REMPLACEMENTS:
        texte = re.sub(motif, remplacement, texte)
    texte = re.sub(r"\b([Jj])e ([aeiouyéèêàâîôûh])", r"\1'\2", texte)          # je étais -> j'étais
    # je portes -> je porte, je ne possèdes -> je ne possède, moi qui donnes -> moi qui donne
    texte = re.sub(r"\b([Jj]e (?:ne |n')?|[Jj]'|moi qui (?:ne )?)(\w+?[^aeious])es\b", r"\1\2e", texte)
    return texte


def mots(texte):
    return {m for m in re.findall(r"[a-zà-ÿ]{4,}", texte.casefold()) if m not in STOPWORDS}


def sections(prompt):
    """{titre de section: [lignes]} du message système (les puces sont retirées)."""
    resultat, courante = {}, None
    for ligne in prompt.splitlines():
        if ligne.startswith("## "):
            courante = resultat.setdefault(ligne[3:].strip(), [])
        elif courante is not None and ligne.strip():
            courante.append(ligne[2:] if ligne.startswith("- ") else ligne)
    return resultat


def generateur_demo(graine=0):
    """Fonction de génération du jeu, sans modèle (même signature que celle du modèle)."""
    rng = random.Random(graine)

    def generer(systeme, historique, question, fiche, secrets_avoues, deja_connu):
        s = sections(systeme)
        maintenant = "\n".join(s.get("Ce qui se passe maintenant", []))
        if "Cette pièce te force à avouer" in maintenant:
            verite = re.search(r"^Vérité : (.+)$", maintenant, re.M).group(1)
            return f"*({rng.choice(AVEU)})* {premiere_personne(verite)}"
        if "aucun de tes secrets" in maintenant:
            return f"*({rng.choice(NEUTRE)})* Je ne vois pas ce que cela a à voir avec moi, inspecteur."
        if maintenant:
            return "Je vous ai déjà tout dit là-dessus, inspecteur."

        q = mots(question)
        for ligne in s.get("Ce que tu penses des autres", []):
            nom, _, avis = ligne.partition(" : ")
            nom = nom.replace(" (la victime)", "")
            if q & mots(nom):
                return f"{nom} ? {premiere_personne(avis)}"
        avoue = [l.split(" Consigne : ")[0] for l in s.get("Ce que tu as déjà avoué", [])]
        candidates = (s.get("Ta version sur les sujets sensibles", []) + avoue
                      + [l.replace("Ton emploi du temps : ", "") for l in s.get("Ce que tu sais et dis volontiers", [])])
        score, meilleure = max(((len(q & mots(c)), c) for c in candidates), default=(0, ""))
        if score >= 2 or (score == 1 and len(q) <= 3):
            return premiere_personne(meilleure)
        return rng.choice(RIEN)

    return generer
