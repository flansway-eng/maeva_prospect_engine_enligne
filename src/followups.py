from typing import Dict
from autogen_agentchat.agents import AssistantAgent

RULES = (
    "RÈGLES ABSOLUES:\n"
    "- N'invente aucune information.\n"
    "- N'utilise que: contact_name, title, company, location, track.\n"
    "- Ton professionnel, pas insistant.\n"
    "- 1 question max.\n"
    "- 450 caractères max.\n"
)

TRACK_LINE = {
    "MA": "Je cible un poste en M&A / Corporate Finance (Associate/Analyst) sur Paris/IDF.",
    "TS": "Je cible Transaction Services / Deal Advisory (TS) sur Paris/IDF.",
    "TT": "Je cible Transaction Tax / M&A Tax (TT) sur Paris/IDF.",
}

STAGE_LINE_FR = {
    1: "Relance courte suite à mon précédent message.",
    2: "Je reviens vers vous une dernière fois pour savoir si le sujet peut vous concerner.",
    3: "Dernière relance de ma part — je clôture ensuite pour ne pas vous déranger.",
}

STAGE_LINE_EN = {
    1: "Just a quick follow-up on my previous message.",
    2: "Following up one last time to see if this could be relevant.",
    3: "Final follow-up from my side — I’ll close the loop after this.",
}

STYLE_GUIDE_FR = {
    "POLITE": "Très poli, très sobre, sans pression.",
    "DIRECT": "Plus direct, orienté action, mais toujours respectueux.",
    "SOFT_CLOSE": "Clôture élégante: propose de fermer si non pertinent.",
}

STYLE_GUIDE_EN = {
    "POLITE": "Very polite and neutral, no pressure.",
    "DIRECT": "More direct, action-oriented, still respectful.",
    "SOFT_CLOSE": "Soft close: offer to close the loop if not relevant.",
}

def make_followup_prompt(lead: Dict, stage: int, lang: str, style: str) -> str:
    track = lead["track"]
    base = TRACK_LINE.get(track, TRACK_LINE["MA"])
    fields = (
        f"CONTACT_NAME: {lead['contact_name']}\n"
        f"TITLE: {lead['title']}\n"
        f"COMPANY: {lead['company']}\n"
        f"LOCATION: {lead.get('location','Paris')}\n"
        f"TRACK: {track}\n"
        f"STAGE: {stage} (1=J+3, 2=J+7, 3=J+14)\n"
        f"STYLE: {style}\n"
    )

    if lang == "FR":
        stage_line = STAGE_LINE_FR.get(stage, STAGE_LINE_FR[1])
        style_line = STYLE_GUIDE_FR.get(style, STYLE_GUIDE_FR["POLITE"])
        return (
            f"Tu écris une relance LinkedIn en français.\n{RULES}\n"
            f"Relance: {stage_line}\nStyle: {style_line}\n"
            f"Pitch: {base}\n"
            f"{fields}\n"
            "Produit: 1 relance courte prête à envoyer."
        )
    else:
        stage_line = STAGE_LINE_EN.get(stage, STAGE_LINE_EN[1])
        style_line = STYLE_GUIDE_EN.get(style, STYLE_GUIDE_EN["POLITE"])
        return (
            f"You write a LinkedIn follow-up in English.\n{RULES}\n"
            f"Follow-up: {stage_line}\nStyle: {style_line}\n"
            f"Pitch: {base}\n"
            f"{fields}\n"
            "Output: one short follow-up ready to send."
        )

async def generate_followup(agent: AssistantAgent, lead: Dict, stage: int, lang: str, style: str) -> str:
    prompt = make_followup_prompt(lead, stage, lang, style)
    r = await agent.run(task=prompt)

    last = ""
    for m in reversed(r.messages):
        if getattr(m, "type", "") == "TextMessage" and getattr(m, "source", "") != "user":
            c = getattr(m, "content", "")
            if isinstance(c, str) and c.strip():
                last = c.strip()
                break
    return last or "(no text)"
