"""Adaptation QLoRA (cahier des charges, §10).

Le modèle de base reste gelé (quantifié en 4 bits sur GPU) ; seuls les paramètres de l'adaptateur
LoRA sont entraînés. La perte ne porte que sur les répliques du personnage : toutes, ou seulement
la dernière quand une pièce est présentée au dernier tour (champ perte_sur, §9.6).

Depuis le notebook (partie 6) :
    from src.train import entrainer
    resultat = entrainer()
"""

import json
import math
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, EarlyStoppingCallback, Trainer, TrainingArguments

from src.config import ENTRAINEMENT, LORA, MAX_LENGTH, MODEL_NAME, SEED
from src.llm import OPTIONS_TEMPLATE, charger_tokenizer, config_4bits

ROOT = Path(__file__).resolve().parent.parent


def lire_jsonl(chemin):
    with open(chemin, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def tokeniser(exemple, tokenizer, max_length=MAX_LENGTH):
    """input_ids et labels : -100 partout sauf sur les répliques du personnage à apprendre.

    Les répliques sont repérées dans le texte rendu par le chat template, puis reportées sur les
    tokens grâce aux positions de caractères (offsets). Renvoie None si l'exemple est trop long.
    """
    messages = exemple["messages"]
    texte = tokenizer.apply_chat_template(messages, tokenize=False, **OPTIONS_TEMPLATE)
    fin_tour = tokenizer.eos_token or ""
    zones, curseur = [], 0
    for i, m in enumerate(messages):
        if m["role"] != "assistant":
            continue
        invite = tokenizer.apply_chat_template(messages[:i], tokenize=False, add_generation_prompt=True,
                                               **OPTIONS_TEMPLATE)
        depart = len(invite) if texte.startswith(invite) else curseur
        debut = texte.index(m["content"], depart)
        fin = debut + len(m["content"])
        if fin_tour and texte.startswith(fin_tour, fin):  # apprendre aussi à s'arrêter
            fin += len(fin_tour)
        zones.append((debut, fin))
        curseur = fin
    if exemple.get("perte_sur") == "dernier":
        zones = zones[-1:]

    encodage = tokenizer(texte, return_offsets_mapping=True, add_special_tokens=False)
    ids = encodage["input_ids"]
    if len(ids) > max_length:
        return None
    labels = [tok if any(debut <= a and b <= fin for debut, fin in zones) and b > a else -100
              for tok, (a, b) in zip(ids, encodage["offset_mapping"])]
    return {"input_ids": ids, "attention_mask": [1] * len(ids), "labels": labels}


class Collateur:
    """Complète les lots à la même longueur (labels complétés par -100)."""

    def __init__(self, pad_id):
        self.pad_id = pad_id

    def __call__(self, lot):
        n = max(len(x["input_ids"]) for x in lot)
        def completer(cle, valeur):
            return torch.tensor([x[cle] + [valeur] * (n - len(x[cle])) for x in lot])
        return {"input_ids": completer("input_ids", self.pad_id),
                "attention_mask": completer("attention_mask", 0),
                "labels": completer("labels", -100)}


def preparer_jeu(chemin, tokenizer, max_length=MAX_LENGTH):
    exemples = [tokeniser(e, tokenizer, max_length) for e in lire_jsonl(chemin)]
    gardes = [e for e in exemples if e is not None]
    return gardes, len(exemples) - len(gardes)


def preparer_modele(nom, gpu):
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    if gpu:
        model = AutoModelForCausalLM.from_pretrained(nom, quantization_config=config_4bits(),
                                                     device_map="auto", dtype=torch.float16)
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    else:
        model = AutoModelForCausalLM.from_pretrained(nom, dtype=torch.float32)
    config = LoraConfig(task_type="CAUSAL_LM", bias="none", **LORA)
    model = get_peft_model(model, config)
    return model


def tracer_courbes(historique, chemin):
    """Courbes de perte (entraînement et validation) pour le notebook et le rapport."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    train = [(h["step"], h["loss"]) for h in historique if "loss" in h]
    val = [(h["step"], h["eval_loss"]) for h in historique if "eval_loss" in h]
    fig, ax = plt.subplots(figsize=(7, 4))
    if train:
        ax.plot(*zip(*train), label="entraînement")
    if val:
        ax.plot(*zip(*val), marker="o", label="validation")
        meilleur = min(val, key=lambda p: p[1])
        ax.axvline(meilleur[0], color="grey", linestyle="--", label=f"meilleur pas ({meilleur[0]})")
    ax.set_xlabel("pas d'optimisation")
    ax.set_ylabel("perte (entropie croisée)")
    ax.set_title("QLoRA : perte d'entraînement et de validation")
    ax.legend()
    fig.tight_layout()
    fig.savefig(chemin, dpi=150)
    plt.close(fig)


def entrainer(nom=MODEL_NAME, train=ROOT / "data" / "train.jsonl", val=ROOT / "data" / "val.jsonl",
              sortie=ROOT / "adapter", resultats=ROOT / "results", max_length=MAX_LENGTH, **surcharges):
    """Entraîne l'adaptateur, garde le meilleur selon la perte de validation et trace les courbes.

    surcharges : remplace des réglages d'ENTRAINEMENT (utile pour un test rapide).
    """
    reglages = {**ENTRAINEMENT, **surcharges}
    gpu = torch.cuda.is_available()
    tokenizer = charger_tokenizer(nom)
    jeu_train, ecartes_train = preparer_jeu(train, tokenizer, max_length)
    jeu_val, ecartes_val = preparer_jeu(val, tokenizer, max_length)
    print(f"entraînement : {len(jeu_train)} exemples ({ecartes_train} trop longs écartés) ; "
          f"validation : {len(jeu_val)} ({ecartes_val} écartés)")

    model = preparer_modele(nom, gpu)
    model.print_trainable_parameters()

    pas_par_epoque = math.ceil(len(jeu_train) / (reglages["per_device_train_batch_size"]
                                                  * reglages["gradient_accumulation_steps"]))
    pas_total = pas_par_epoque * reglages["num_train_epochs"]
    sortie, resultats = Path(sortie), Path(resultats)
    arguments = TrainingArguments(
        output_dir=str(ROOT / "checkpoints"),
        per_device_train_batch_size=reglages["per_device_train_batch_size"],
        per_device_eval_batch_size=reglages["per_device_train_batch_size"],
        gradient_accumulation_steps=reglages["gradient_accumulation_steps"],
        learning_rate=reglages["learning_rate"],
        num_train_epochs=reglages["num_train_epochs"],
        max_steps=reglages.get("max_steps", -1),
        lr_scheduler_type="cosine",
        warmup_steps=max(1, int(reglages["part_echauffement"] * pas_total)),
        eval_strategy="steps",
        eval_steps=reglages["eval_steps"],
        save_strategy="steps",
        save_steps=reglages["eval_steps"],
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        logging_steps=max(1, reglages["eval_steps"] // 2),
        fp16=gpu,
        gradient_checkpointing=gpu,
        gradient_checkpointing_kwargs={"use_reentrant": False} if gpu else None,
        optim="paged_adamw_8bit" if gpu else "adamw_torch",
        report_to="none",
        seed=SEED,
        remove_unused_columns=False,
    )
    trainer = Trainer(
        model=model,
        args=arguments,
        train_dataset=jeu_train,
        eval_dataset=jeu_val,
        data_collator=Collateur(tokenizer.pad_token_id),
        processing_class=tokenizer,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=reglages["patience"])],
    )
    trainer.train()

    sortie.mkdir(parents=True, exist_ok=True)
    resultats.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(sortie))  # le meilleur adaptateur (load_best_model_at_end)
    tokenizer.save_pretrained(str(sortie))
    historique = trainer.state.log_history
    (resultats / "historique_entrainement.json").write_text(
        json.dumps(historique, ensure_ascii=False, indent=1), encoding="utf-8")
    tracer_courbes(historique, resultats / "courbes_loss.png")
    val_pertes = [(h["step"], h["eval_loss"]) for h in historique if "eval_loss" in h]
    meilleur = min(val_pertes, key=lambda p: p[1]) if val_pertes else (None, None)
    bilan = {"meilleur_pas": meilleur[0], "meilleure_perte_val": meilleur[1],
             "pas_effectues": trainer.state.global_step, "pas_par_epoque": pas_par_epoque,
             "exemples_train": len(jeu_train), "exemples_val": len(jeu_val),
             "arret_anticipe": trainer.state.global_step < (reglages.get("max_steps", -1) if reglages.get("max_steps", -1) > 0 else pas_total)}
    (resultats / "bilan_entrainement.json").write_text(json.dumps(bilan, indent=1), encoding="utf-8")
    print(bilan)
    return bilan


def publier_adaptateur(dossier, depot):
    """Publie l'adaptateur sur le Hugging Face Hub (après `huggingface-cli login`)."""
    from huggingface_hub import HfApi
    api = HfApi()
    api.create_repo(depot, exist_ok=True)
    api.upload_folder(folder_path=str(dossier), repo_id=depot)
    return f"https://huggingface.co/{depot}"
