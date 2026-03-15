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
    "- Évite explicitement les mots: postule, candidature, recrutement, emploi, job.\n"
)

# Pitch volontairement "marché" (pas 'je postule / recrutez-vous')
TRACK_PITCH = {
    "MA": "Je m’intéresse aux sujets M&A / Corporate Finance à Paris/IDF et je souhaite mieux comprendre les priorités des équipes.",
    "TS": "Je travaille mon positionnement en Transaction Services (FDD/QoE/WC) à Paris/IDF et je souhaite comprendre les pratiques terrain.",
    "TT": "Je me spécialise en Transaction Tax / M&A Tax à Paris/IDF et je souhaite comprendre les sujets TT récurrents côté deal.",
}

# Hook (vocabulaire crédible) par track
TRACK_HOOK = {
    "MA": "Angle: M&A / Corporate Finance (exécution, process, dynamique d’équipe, mid-cap / sector coverage).",
    "TS": "Angle: Transaction Services / FDD (QoE, working capital, closing accounts, carve-out).",
    "TT": "Angle: Transaction Tax / M&A Tax (due diligence fiscale, SPA tax, restructurations, management packages).",
}

# 1 question MAX (CTA) par track + persona
TRACK_ASKS_FR = {
    "MA": {
        "DECIDER": "Seriez-vous ouverte à un bref échange de 10 minutes pour comprendre les priorités de votre équipe sur les sujets M&A ?",
        "RELAY":   "Auriez-vous 10 minutes pour partager votre retour sur les compétences clés attendues sur vos dossiers M&A ?",
        "PEER":    "Seriez-vous d’accord pour un échange de 10 minutes afin de comparer les pratiques et le quotidien sur des dossiers M&A ?",
    },
    "TS": {
        "DECIDER": "Seriez-vous ouverte à un bref échange de 10 minutes sur vos sujets TS les plus fréquents (QoE/WC) ?",
        "RELAY":   "Auriez-vous 10 minutes pour partager comment vous structurez une mission FDD (QoE/WC) dans votre équipe ?",
        "PEER":    "Seriez-vous d’accord pour un échange de 10 minutes sur vos méthodes QoE/WC et le quotidien TS ?",
    },
    "TT": {
        "DECIDER": "Seriez-vous ouverte à un bref échange de 10 minutes sur les sujets TT récurrents (DD/SPA/restructuration) ?",
        "RELAY":   "Auriez-vous 10 minutes pour partager les sujets TT que vous voyez le plus en pratique sur vos deals ?",
        "PEER":    "Seriez-vous d’accord pour un échange de 10 minutes sur les sujets TT (DD/SPA) et vos méthodes de travail ?",
    },
}

TRACK_ASKS_EN = {
    "MA": {
        "DECIDER": "Would you be open to a brief 10-minute chat to understand your team’s current priorities in M&A?",
        "RELAY":   "Would you have 10 minutes to share what skills matter most on your M&A engagements?",
        "PEER":    "Would you be open to a brief 10-minute chat to compare day-to-day practices on M&A deals?",
    },
    "TS": {
        "DECIDER": "Would you be open to a brief 10-minute chat about your most frequent TS topics (QoE / working capital)?",
        "RELAY":   "Would you have 10 minutes to share how your team structures an FDD engagement (QoE / WC)?",
        "PEER":    "Would you be open to a brief 10-minute chat about QoE/WC methods and TS day-to-day work?",
    },
    "TT": {
        "DECIDER": "Would you be open to a brief 10-minute chat about recurring TT topics (DD / SPA / restructuring)?",
        "RELAY":   "Would you have 10 minutes to share the TT topics you most often see in practice on deals?",
        "PEER":    "Would you be open to a brief 10-minute chat about TT topics (DD/SPA) and your working methods?",
    },
}

def _norm_track(track: str) -> str:
    t = (track or "MA").strip().upper()
    return t if t in ("MA", "TS", "TT") else "MA"

def _norm_persona(persona: str) -> str:
    p = (persona or "PEER").strip().upper()
    return p if p in PERSONAS else "PEER"

def pick_hook(track: str) -> str:
    t = _norm_track(track)
    return TRACK_HOOK[t]

def pick_ask(track: str, persona: str, lang: str) -> str:
    t = _norm_track(track)
    p = _norm_persona(persona)
    if lang == "FR":
        return TRACK_ASKS_FR[t][p]
    return TRACK_ASKS_EN[t][p]

def make_prompt(lead: Dict, persona: str, lang: str, variant: str) -> str:
    track = _norm_track(lead.get("track", "MA"))
    persona = _norm_persona(persona)
    variant = (variant or "STANDARD").strip().upper()
    if variant not in VARIANTS:
        variant = "STANDARD"

    base = TRACK_PITCH.get(track, TRACK_PITCH["MA"])
    who = PERSONAS[persona]
    how = VARIANTS[variant]

    hook = pick_hook(track)
    ask = pick_ask(track, persona, lang)

    fields = (
        f"CONTACT_NAME: {lead.get('contact_name','')}\n"
        f"TITLE: {lead.get('title','')}\n"
        f"COMPANY: {lead.get('company','')}\n"
        f"LOCATION: {lead.get('location','Paris')}\n"
        f"TRACK: {track}\n"
    )

    if lang == "FR":
        return (
            f"Tu écris un message LinkedIn en français.\n{RULES}\n"
            f"Persona: {who}\nVariant: {variant} — {how}\n"
            f"Pitch: {base}\n"
            f"Hook: {hook}\n"
            f"Question (1 max): {ask}\n"
            f"{fields}\n"
            "Produit: 1 message prêt à envoyer. "
            "Intègre exactement la question ci-dessus (1 seule). "
            "Pas de sujet. Signature courte (optionnelle)."
        )
    else:
        return (
            f"You write a LinkedIn message in English.\n{RULES}\n"
            f"Persona: {who}\nVariant: {variant} — {how}\n"
            f"Pitch: {base}\n"
            f"Hook: {hook}\n"
            f"Single question (max 1): {ask}\n"
            f"{fields}\n"
            "Output: one ready-to-send message. "
            "Include exactly the single question above (max 1). "
            "No subject. Short sign-off optional."
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
