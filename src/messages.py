from typing import Dict
from autogen_agentchat.agents import AssistantAgent

PERSONAS = {
    "DECIDER": "Décideur (Partner/Director/MD) — objectif: renvoi vers la bonne personne OU micro-call.",
    "RELAY": "Relais (Manager/Senior) — objectif: conseils + referral interne.",
    "PEER": "Peer (Associate/Analyst) — objectif: échange pair-à-pair + referral.",
}

VARIANTS = {
    "ULTRA": "Ultra court, direct, ≤ 250 caractères.",
    "STANDARD": "Standard, professionnel, ≤ 500 caractères.",
    "WARM": "Plus chaleureux, humain, ≤ 700 caractères, sans familiarité excessive.",
}

RULES = (
    "RÈGLES ABSOLUES:\n"
    "- N'invente aucune information (école, deals, email, numéro, etc.).\n"
    "- N'utilise que: contact_name, title, company, location, track.\n"
    "- 1 question max.\n"
    "- Pas de pression. Ton sobre.\n"
)

TRACK_PITCH = {
    "MA": "Je cible un poste en M&A / Corporate Finance (Associate/Analyst) sur Paris/IDF.",
    "TS": "Je cible Transaction Services / Deal Advisory (TS) sur Paris/IDF.",
    "TT": "Je cible Transaction Tax / M&A Tax (TT) sur Paris/IDF.",
}

def make_prompt(lead: Dict, persona: str, lang: str, variant: str) -> str:
    track = lead["track"]
    base = TRACK_PITCH.get(track, TRACK_PITCH["MA"])
    who = PERSONAS[persona]
    how = VARIANTS[variant]
    fields = (
        f"CONTACT_NAME: {lead['contact_name']}\n"
        f"TITLE: {lead['title']}\n"
        f"COMPANY: {lead['company']}\n"
        f"LOCATION: {lead.get('location','Paris')}\n"
        f"TRACK: {track}\n"
    )

    if lang == "FR":
        return (
            f"Tu écris un message LinkedIn en français.\n{RULES}\n"
            f"Persona: {who}\nVariant: {variant} — {how}\n"
            f"Pitch: {base}\n"
            f"{fields}\n"
            "Produit: 1 message prêt à envoyer. Pas de sujet. Signature courte (optionnelle)."
        )
    else:
        return (
            f"You write a LinkedIn message in English.\n{RULES}\n"
            f"Persona: {who}\nVariant: {variant} — {how}\n"
            f"Pitch: {base}\n"
            f"{fields}\n"
            "Output: one ready-to-send message. No subject. Short sign-off optional."
        )

async def generate_message(agent: AssistantAgent, lead: Dict, persona: str, lang: str, variant: str) -> str:
    prompt = make_prompt(lead, persona, lang, variant)
    r = await agent.run(task=prompt)

    last = ""
    for m in reversed(r.messages):
        if getattr(m, "type", "") == "TextMessage" and getattr(m, "source", "") != "user":
            c = getattr(m, "content", "")
            if isinstance(c, str) and c.strip():
                last = c.strip()
                break

    return last or "(no text)"
