"""Mode démo : des réponses sans modèle de langage, tirées du message système du personnage.

Il sert à essayer l'interface et à tester une affaire sans GPU. Le personnage répond à la première
personne avec ce que contient son prompt : sa version officielle sur les sujets sensibles, ce qu'il sait,
son opinion sur les autres, et ses aveux quand on lui montre la bonne pièce. Quelques mots-clés lui font
reconnaître les questions courantes (sa soirée, le coupable, ce qu'il a remarqué). Comme le prompt ne
contient jamais un secret verrouillé ni la solution (barrières 2 et 3), le mode démo ne peut rien divulguer.
"""

import random
import re

STOPWORDS = set("""avec dans pour pendant cette votre vous nous elle elles ils mais donc comme quand quoi
quel quelle quels quelles avez aviez était étiez êtes sont tout tous toute toutes alors aussi encore
leur leurs chez être avoir fait faire plus moins très bien vers sans sous sur entre depuis jamais rien
monsieur madame mademoiselle inspecteur soir soirée""".split())

# Didascalies sans pronom : elles conviennent aux personnages des deux sexes.
AVEU = ["Un long silence.", "Les yeux baissés.", "La voix se brise.", "Un temps.", "Un silence, puis l'aveu."]
NEUTRE = ["Un haussement d'épaules.", "Un regard étonné.", "Un temps.", "Un froncement de sourcils."]
RIEN = ["Je n'en sais rien, inspecteur.", "Là, vous m'en demandez trop : je n'en sais rien.",
        "Je ne saurais vous dire, inspecteur."]
TITRES = {"m", "mme", "mlle", "monsieur", "madame", "mademoiselle", "dr", "docteur", "commissaire", "maître"}
# Les questions les plus courantes (dont celles que suggère l'interface), reconnues par quelques mots.
INTENTIONS = [
    ("coupable", re.compile(r"\b(tué|tuer|tueur|assassin\w*|coupable|meurtri\w+)\b", re.I)),
    ("soiree", re.compile(r"\b(soirée|racontez|emploi du temps|alibi|étiez|trouviez|faisiez)\b"
                          r"|moment du (drame|crime|meurtre)", re.I)),
    ("remarque", re.compile(r"\b(remarqué|inhabituel|étrange|bizarre|curieux)\b|vu quelque chose", re.I)),
    ("rancune", re.compile(r"en vouloir|\bennemis?\b|rancune|\bhaï|détest", re.I)),
]

# Deuxième personne de la fiche -> première personne de la réplique (approximatif, mais lisible).
REMPLACEMENTS = [
    (r"\bTu n'as\b", "Je n'ai"), (r"\btu n'as\b", "je n'ai"), (r"\bTu n'es\b", "Je ne suis"),
    (r"\btu n'es\b", "je ne suis"), (r"\bTu t'es\b", "Je me suis"), (r"\btu t'es\b", "je me suis"),
    (r"\bTu as\b", "J'ai"), (r"\btu as\b", "j'ai"), (r"\bTu es\b", "Je suis"), (r"\btu es\b", "je suis"),
    (r"\bTu l'as\b", "Je l'ai"), (r"\btu l'as\b", "je l'ai"), (r"\bTu vas\b", "Je vais"), (r"\btu vas\b", "je vais"),
    (r"\bt'", "m'"), (r"\bte\b", "me"), (r"\btoi\b", "moi"), (r"\bTon\b", "Mon"), (r"\bton\b", "mon"),
    (r"\bTa\b", "Ma"), (r"\bta\b", "ma"), (r"\bTes\b", "Mes"), (r"\btes\b", "mes"),
    (r"\bTu\b", "Je"), (r"\btu\b", "je"), (r"\bmoi qui as\b", "moi qui ai"), (r"\bmoi qui es\b", "moi qui suis"),
]


def premiere_personne(texte):
    for motif, remplacement in REMPLACEMENTS:
        texte = re.sub(motif, remplacement, texte)
    texte = re.sub(r"\b([Jj])e ([aeiouyéèêàâîôûh])", r"\1'\2", texte)          # je étais -> j'étais
    # je portes -> je porte, je ne possèdes -> je ne possède, moi qui donnes -> moi qui donne, j'en parles -> j'en parle
    texte = re.sub(r"\b((?:[Jj]e |[Jj]'|moi qui )(?:ne |n')?(?:en |y |le |la |les |lui |leur |l'|m')?)"
                   r"(\w+?[^aeious])es\b", r"\1\2e", texte)
    return texte


def mots(texte):
    return {m for m in re.findall(r"[a-zà-ÿ]{4,}", texte.casefold()) if m not in STOPWORDS}


def mention(question, nom):
    """2 si la question cite le prénom, 1 le seul nom de famille, 0 sinon.

    « Rose Delorme » ne désigne pas Victor Delorme : un nom de famille précédé d'un autre prénom ne compte pas.
    """
    prenom, *famille = nom.split()
    q = mots(question)
    if mots(prenom) & q:
        return 2
    for partie in famille:
        if mots(partie) & q:
            avant = re.findall(rf"(\S+)\s+{re.escape(partie)}\b", question, re.I)
            if any(a[0].isupper() and a.strip(".").casefold() not in TITRES for a in avant):
                return 0
            return 1
    return 0


def avis_sur(lignes, question):
    """Opinion du personnage sur la personne que cite la question (lignes « Nom : avis »), ou None."""
    avis = []
    for ligne in lignes:
        nom, _, opinion = ligne.partition(" : ")
        nom = nom.replace(" (la victime)", "")
        avis.append((mention(question, nom), nom, opinion))
    meilleur = max((a[0] for a in avis), default=0)
    cites = [a for a in avis if a[0] == meilleur]
    if meilleur == 2 or (meilleur == 1 and len(cites) == 1):
        _, nom, opinion = cites[0]
        return f"{nom} ? {premiere_personne(opinion)}"
    if meilleur == 1:                           # « Mme Delorme » : plusieurs personnes portent ce nom
        return "Ils sont plusieurs à porter ce nom ce soir, inspecteur : de qui parlez-vous ?"
    return None


def sur_le_coupable(version, question):
    """Le prompt ne contient jamais la solution : le personnage l'ignore, ou nie s'il est soupçonné."""
    if re.search(r"(avez|êtes)-vous|vous (l'avez|avez|êtes)", question, re.I):   # « Avez-vous tué… ? »
        dementi = [l for l in version if re.search(r"\bmort\b|rien à voir", l)]
        return premiere_personne(dementi[0]) if dementi else "Moi ? Certainement pas, inspecteur."
    return "Je ne sais pas qui a fait ça, inspecteur : c'est à vous de le trouver."


def reponse_type(intention, s, question, rng):
    """Réplique pour une question courante, tirée des sections du prompt ; None si rien ne convient."""
    sait = s.get("Ce que tu sais et dis volontiers", [])
    version = s.get("Ta version sur les sujets sensibles", [])
    emploi = [l.replace("Ton emploi du temps : ", "") for l in sait if l.startswith("Ton emploi du temps")]
    faits = [l for l in sait if not l.startswith("Ton emploi du temps")]
    if intention == "coupable":
        return sur_le_coupable(version, question)
    if intention == "soiree":                   # l'emploi du temps, et la version officielle sur le moment clé
        moment = [l for l in version if re.match(r"(Pendant|Au discours|À \d|Entre \d|De \d)", l)]
        texte = " ".join(emploi[:1] + moment[:1])
        return premiere_personne(texte) if texte else None
    if intention == "remarque":                 # de préférence un fait daté
        choix = [l for l in faits if re.search(r"\d{1,2}h", l)] or faits
        return premiere_personne(rng.choice(choix)) if choix else None
    if intention == "rancune":                  # une insinuation sur quelqu'un d'autre que la victime
        autres = [l for l in s.get("Ce que tu penses des autres", []) if "(la victime)" not in l]
        if autres:
            nom, _, opinion = rng.choice(autres).partition(" : ")
            return f"{nom} ? {premiere_personne(opinion)}"
    return None


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

        intention = next((nom for nom, motif in INTENTIONS if motif.search(question)), None)
        reponse = (reponse_type(intention, s, question, rng) if intention else None) \
            or avis_sur(s.get("Ce que tu penses des autres", []), question)
        if reponse:
            return reponse
        q = mots(question)
        avoue = [l.split(" Consigne : ")[0] for l in s.get("Ce que tu as déjà avoué", [])]
        candidates = (s.get("Ta version sur les sujets sensibles", []) + avoue
                      + [l.replace("Ton emploi du temps : ", "") for l in s.get("Ce que tu sais et dis volontiers", [])])
        score, meilleure = max(((len(q & mots(c)), c) for c in candidates), default=(0, ""))
        if score >= 2 or (score == 1 and len(q) <= 3):
            return premiere_personne(meilleure)
        return rng.choice(RIEN)

    return generer
