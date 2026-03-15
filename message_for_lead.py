import argparse
import pandas as pd
from datetime import date
from src.store import load_pipeline
from src.llm import chat_json  # adapte si ton projet a un autre wrapper

def build_prompt(row: dict, mode: str, stage: int) -> str:
    track = row.get("track","")
    contact = row.get("contact_name","")
    company = row.get("company","")
    title = row.get("title","")
    notes = row.get("notes","")
    loc = row.get("location","")

    base = f"""
You are an expert career outreach assistant for Paris/IDF market.
Write ultra-short LinkedIn messages (<= 600 chars) in FR and EN.
No emojis. Polite. Human. No hype.
Context:
- Track: {track} (MA= M&A Associate, TS=Transaction Services, TT=Transaction Tax)
- Contact: {contact}
- Company: {company}
- Title: {title}
- Location: {loc}
- Notes: {notes}
"""

    if mode == "OUTREACH":
        task = """
Goal: initial outreach message.
Produce 3 variants: ULTRA, STANDARD, WARM for FR and EN.
Each variant must include:
- 1 line hook (why them)
- 1 ask (10-min call OR point me to right person)
- signature placeholder [Your Name]
Return JSON with keys: fr_ultra, fr_standard, fr_warm, en_ultra, en_standard, en_warm
"""
    else:
        task = f"""
Goal: follow-up message for a previous outreach.
Stage = {stage}:
- Stage 1: polite reminder
- Stage 2: direct ask for 10-min call
- Stage 3: soft close ("if not a priority, I will close the loop")
Return JSON with keys: fr, en
"""

    return base + "\n" + task.strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lead-id", required=True)
    ap.add_argument("--mode", choices=["OUTREACH","FOLLOWUP"], required=True)
    ap.add_argument("--stage", type=int, default=1)
    args = ap.parse_args()

    df = load_pipeline()
    df["lead_id"] = df["lead_id"].astype(str)
    row = df[df["lead_id"] == str(args.lead_id)]
    if row.empty:
        raise SystemExit("lead_id not found")

    r = row.iloc[0].to_dict()
    prompt = build_prompt(r, args.mode, int(args.stage))

    data = chat_json(prompt)  # doit retourner dict
    print(data)

if __name__ == "__main__":
    main()
