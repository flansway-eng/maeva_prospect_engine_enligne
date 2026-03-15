import asyncio
import json
import re
from typing import Any, Dict

from autogen_agentchat.agents import AssistantAgent
from src.llm_client import make_deepseek_client


def _extract_json(text: str) -> Dict[str, Any]:
    """
    Extraction robuste d'un JSON depuis une réponse LLM (gère texte autour / code fences).
    """
    if not text:
        raise ValueError("Empty LLM output")

    # Supprime fences ```json ... ```
    t = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE).replace("```", "").strip()

    # Cherche le premier { ... dernier }
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in LLM output")

    blob = t[start : end + 1]
    return json.loads(blob)


def _system_message() -> str:
    return (
        "Tu es un assistant expert en prospection LinkedIn (Paris/IDF) pour profils M&A / TS / TT. "
        "Tu écris des messages courts, polis, humains, sans emojis, sans hype. "
        "Tu renvoies STRICTEMENT du JSON valide (pas de texte autour)."
    )


async def _run_llm_json(prompt: str) -> Dict[str, Any]:
    client = make_deepseek_client()
    agent = AssistantAgent(
        name="msg_agent",
        model_client=client,
        system_message=_system_message(),
    )
    result = await agent.run(task=prompt)

    # Récupère le dernier message textuel NON-user (AutoGen met souvent source="msg_agent")
    final_text = None
    msgs = list(getattr(result, "messages", []) or [])

    for m in reversed(msgs):
        src = getattr(m, "source", None)
        c = getattr(m, "content", None)
        if src in ("user", None):
            continue
        if isinstance(c, str) and c.strip():
            final_text = c
            break

    if not final_text:
        # Debug minimal: types/sources visibles
        debug = [(type(m).__name__, getattr(m, "source", None), getattr(m, "type", None)) for m in msgs]
        raise RuntimeError(f"No final text message found. messages={debug}")

    return _extract_json(final_text)


def build_outreach_prompt(row: dict) -> str:
    track = row.get("track", "")
    contact = row.get("contact_name", "")
    company = row.get("company", "")
    title = row.get("title", "")
    location = row.get("location", "")
    notes = row.get("notes", "")

    return f"""
Contexte:
- Track: {track} (MA=M&A, TS=Transaction Services, TT=Transaction Tax)
- Contact: {contact}
- Company: {company}
- Title: {title}
- Location: {location}
- Notes: {notes}

Tâche:
Génère des messages LinkedIn d'approche INITIAL (premier contact).
Contraintes:
- FR et EN
- 3 tons: ULTRA, STANDARD, WARM
- <= 600 caractères chacun
- 1 hook (pourquoi cette personne), 1 ask (10 min call OU pointer vers la bonne personne), signature [Your Name]
- Sortie: JSON STRICT, clés:
  fr_ultra, fr_standard, fr_warm, en_ultra, en_standard, en_warm
Rends STRICTEMENT du JSON valide.
""".strip()


def build_followup_prompt(row: dict, stage: int) -> str:
    track = row.get("track", "")
    contact = row.get("contact_name", "")
    company = row.get("company", "")
    title = row.get("title", "")
    location = row.get("location", "")
    notes = row.get("notes", "")

    return f"""
Contexte:
- Track: {track} (MA=M&A, TS=Transaction Services, TT=Transaction Tax)
- Contact: {contact}
- Company: {company}
- Title: {title}
- Location: {location}
- Notes: {notes}
- Follow-up stage: {stage}

Tâche:
Génère un message de RELANCE LinkedIn (après un premier message).
Règles par stage:
- Stage 1: relance polie (rappel + question courte)
- Stage 2: relance directe (propose call 10 min)
- Stage 3: soft close (si pas prioritaire, je clôture la boucle)
Contraintes:
- FR et EN
- <= 600 caractères
- Sortie: JSON STRICT, clés: fr, en
Rends STRICTEMENT du JSON valide.
""".strip()


def generate_outreach_json(row: dict) -> Dict[str, Any]:
    prompt = build_outreach_prompt(row)
    return asyncio.run(_run_llm_json(prompt))


def generate_followup_json(row: dict, stage: int) -> Dict[str, Any]:
    prompt = build_followup_prompt(row, stage)
    return asyncio.run(_run_llm_json(prompt))

def guess_followup_stage(lead_id: str) -> int:
    """
    Heuristique simple: events.csv si dispo.
    stage = 1 + nb d'événements followup déjà envoyés, borné à 3.
    """
    from pathlib import Path
    import pandas as pd

    events = Path("data/events.csv")
    if not events.exists():
        return 1
    try:
        df = pd.read_csv(events)
        if "lead_id" not in df.columns or "event" not in df.columns:
            return 1
        rows = df[df["lead_id"].astype(str) == str(lead_id)]
        if rows.empty:
            return 1
        ev = rows["event"].astype(str).str.lower()
        c = int(ev.str.contains("followup").sum())
        return min(c + 1, 3)
    except Exception:
        return 1

def build_reply_handler_prompt(row: dict, inbound_reply: str) -> str:
    track = row.get("track", "")
    contact = row.get("contact_name", "")
    company = row.get("company", "")
    title = row.get("title", "")
    location = row.get("location", "")
    notes = row.get("notes", "")

    return f"""
Contexte:
- Track: {track}
- Contact: {contact}
- Company: {company}
- Title: {title}
- Location: {location}
- Notes: {notes}

Message reçu (copié-collé):
\"\"\"{inbound_reply}\"\"\"

Tâche:
1) Analyse courte: intention (interest / referral / no / needs info / scheduling), ton, prochaine action.
2) Propose une réponse LinkedIn FR et EN (<= 700 caractères), polie, claire, sans emojis, avec un call-to-action adapté.
3) Recommande une action pipeline parmi:
   - MARK_REPLIED_STOP (si la conversation continue et on stop les followups automatiques)
   - MARK_SENT_J3 (si on a répondu mais on veut planifier une relance)
   - DO_NOT_CONTACT (si refus explicite)
Sortie: JSON STRICT avec clés:
  analysis_intent, analysis_next_step,
  reply_fr, reply_en,
  recommended_action
Rends STRICTEMENT du JSON valide.
""".strip()


def generate_reply_handler_json(row: dict, inbound_reply: str):
    prompt = build_reply_handler_prompt(row, inbound_reply)
    return asyncio.run(_run_llm_json(prompt))

def generate_outreach_trackaware(row: dict, persona: str = "DECIDER") -> dict:
    """
    OUTREACH track-aware basé sur src/messages.py (Hook + Ask par track/persona).
    Retourne un dict: fr_ultra, fr_standard, fr_warm, en_ultra, en_standard, en_warm.
    """
    import asyncio
    from autogen_agentchat.agents import AssistantAgent
    from src.llm_client import make_deepseek_client
    from src.messages import generate_message

    # Agent "texte" (pas JSON)
    client = make_deepseek_client()
    agent = AssistantAgent(
        name="msg_agent_text",
        model_client=client,
        system_message=(
            "Tu suis STRICTEMENT le prompt fourni. "
            "Retourne uniquement le message final, sans JSON, sans markdown, sans titre."
        ),
    )

    lead = {
        "track": row.get("track", "MA"),
        "contact_name": row.get("contact_name", ""),
        "title": row.get("title", ""),
        "company": row.get("company", ""),
        "location": row.get("location", "Paris"),
    }

    async def _run():
        out = {}
        out["fr_ultra"] = await generate_message(agent, lead, persona=persona, lang="FR", variant="ULTRA")
        out["fr_standard"] = await generate_message(agent, lead, persona=persona, lang="FR", variant="STANDARD")
        out["fr_warm"] = await generate_message(agent, lead, persona=persona, lang="FR", variant="WARM")
        out["en_ultra"] = await generate_message(agent, lead, persona=persona, lang="EN", variant="ULTRA")
        out["en_standard"] = await generate_message(agent, lead, persona=persona, lang="EN", variant="STANDARD")
        out["en_warm"] = await generate_message(agent, lead, persona=persona, lang="EN", variant="WARM")
        return out

    return asyncio.run(_run())

def generate_outreach_trackaware(row: dict, persona: str = "DECIDER") -> dict:
    """
    OUTREACH track-aware basé sur src/messages.py (Hook + Ask par track/persona).
    Retourne un dict: fr_ultra, fr_standard, fr_warm, en_ultra, en_standard, en_warm.
    """
    import asyncio
    from autogen_agentchat.agents import AssistantAgent
    from src.llm_client import make_deepseek_client
    from src.messages import generate_message

    # Agent "texte" (pas JSON)
    client = make_deepseek_client()
    agent = AssistantAgent(
        name="msg_agent_text",
        model_client=client,
        system_message=(
            "Tu suis STRICTEMENT le prompt fourni. "
            "Retourne uniquement le message final, sans JSON, sans markdown, sans titre."
        ),
    )

    lead = {
        "track": row.get("track", "MA"),
        "contact_name": row.get("contact_name", ""),
        "title": row.get("title", ""),
        "company": row.get("company", ""),
        "location": row.get("location", "Paris"),
    }

    async def _run():
        out = {}
        out["fr_ultra"] = await generate_message(agent, lead, persona=persona, lang="FR", variant="ULTRA")
        out["fr_standard"] = await generate_message(agent, lead, persona=persona, lang="FR", variant="STANDARD")
        out["fr_warm"] = await generate_message(agent, lead, persona=persona, lang="FR", variant="WARM")
        out["en_ultra"] = await generate_message(agent, lead, persona=persona, lang="EN", variant="ULTRA")
        out["en_standard"] = await generate_message(agent, lead, persona=persona, lang="EN", variant="STANDARD")
        out["en_warm"] = await generate_message(agent, lead, persona=persona, lang="EN", variant="WARM")
        return out

    return asyncio.run(_run())
