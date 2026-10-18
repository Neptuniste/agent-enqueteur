"""Chargement du modèle (et de l'adaptateur LoRA) et génération (cahier des charges, §8).

Sur GPU : modèle quantifié en 4 bits NF4, calcul en float16 (adapté au T4 de Colab).
Sur CPU (tests locaux) : modèle en float32, plus lent mais utilisé de la même façon.
"""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from src.config import GENERATION_KWARGS, MAX_CONTEXT, MAX_HISTORY_TURNS, MODEL_NAME
from src.guard import generer_sans_fuite

# Variable transmise au chat template : coupe le mode « thinking » des modèles Qwen3 hybrides,
# sans effet sur les autres modèles.
OPTIONS_TEMPLATE = {"enable_thinking": False}


def config_4bits():
    from transformers import BitsAndBytesConfig
    return BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                              bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)


def charger_tokenizer(nom=MODEL_NAME):
    tokenizer = AutoTokenizer.from_pretrained(nom)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer


def charger_modele(nom=MODEL_NAME, adaptateur=None, quantifier=None):
    """Renvoie (modèle, tokenizer). adaptateur : dossier local ou dépôt Hugging Face d'un adaptateur LoRA."""
    tokenizer = charger_tokenizer(nom)
    gpu = torch.cuda.is_available()
    if quantifier if quantifier is not None else gpu:
        model = AutoModelForCausalLM.from_pretrained(
            nom, quantization_config=config_4bits(), device_map="auto", dtype=torch.float16)
    else:
        model = AutoModelForCausalLM.from_pretrained(
            nom, dtype=torch.float16 if gpu else torch.float32, device_map="auto" if gpu else None)
    if adaptateur:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, adaptateur)
    model.eval()
    return model, tokenizer


def longueur(tokenizer, messages):
    """Nombre de tokens d'une conversation, invite de génération comprise."""
    ids = tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=True, **OPTIONS_TEMPLATE)
    if hasattr(ids, "keys"):  # certaines versions renvoient un dictionnaire
        ids = ids["input_ids"]
    return len(ids)


def construire_messages(systeme, historique, question, tokenizer=None,
                        max_echanges=MAX_HISTORY_TURNS, max_contexte=MAX_CONTEXT,
                        max_reponse=GENERATION_KWARGS["max_new_tokens"]):
    """Message système + derniers échanges + question (§8.4).

    On garde au plus max_echanges échanges (question du joueur + réponse), puis on retire les plus
    anciens tant que le contexte dépasse max_contexte. Les aveux, eux, restent dans le message système.
    """
    garde = list(historique)[-2 * max_echanges:] if max_echanges else []
    while True:
        messages = [{"role": "system", "content": systeme}, *garde, {"role": "user", "content": question}]
        if tokenizer is None or not garde or longueur(tokenizer, messages) + max_reponse <= max_contexte:
            return messages
        garde = garde[2:]


def generer_tirages(model, tokenizer, messages, tirages=1, graine=None, **reglages):
    """Applique le chat template et renvoie `tirages` réponses, générées en un seul appel."""
    params = {**GENERATION_KWARGS, **reglages}
    glouton = params.get("temperature") == 0
    if glouton:  # décodage glouton (argmax) : tous les tirages seraient identiques
        params = {k: v for k, v in params.items() if k not in ("temperature", "top_p", "top_k")}
        params["do_sample"] = False
    entree = tokenizer.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt",
                                           return_dict=True, **OPTIONS_TEMPLATE).to(model.device)
    if graine is not None:
        torch.manual_seed(graine)
    with torch.no_grad():
        sortie = model.generate(**entree, **params, num_return_sequences=1 if glouton else tirages,
                                pad_token_id=tokenizer.pad_token_id)
    debut = entree["input_ids"].shape[1]
    textes = [tokenizer.decode(s[debut:], skip_special_tokens=True).strip() for s in sortie]
    return textes * tirages if glouton else textes


def generer(model, tokenizer, messages, graine=None, **reglages):
    """Applique le chat template, génère et renvoie le texte de la réponse."""
    return generer_tirages(model, tokenizer, messages, 1, graine, **reglages)[0]


def repondre(model, tokenizer, systeme, historique, question, fiche=None, secrets_avoues=(),
             deja_connu="", graine=None, filtrer=True, **reglages):
    """Réponse du personnage, avec le filtre de sortie (barrière 4) si une fiche est fournie.

    Renvoie (réponse, nombre de régénérations dues au filtre).
    """
    messages = construire_messages(systeme, historique, question, tokenizer)
    essai = [0]

    def un_essai():
        g = None if graine is None else graine + 1000 * essai[0]  # nouvelle graine à chaque régénération
        essai[0] += 1
        return generer(model, tokenizer, messages, graine=g, **reglages)

    if filtrer and fiche is not None:
        return generer_sans_fuite(un_essai, fiche, secrets_avoues, deja_connu + " " + question)
    return un_essai(), 0
