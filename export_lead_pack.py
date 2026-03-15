import argparse
import json
import re
from pathlib import Path
from datetime import datetime

import pandas as pd

from src.store import load_pipeline  # ton store existant

HIST_DIR = Path("data/conversations")
OUT_DIR = Path("out")


def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _read_history(lead_id: str) -> str:
    p = HIST_DIR / f"{lead_id}.md"
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


def _extract_events(txt: str):
    # Lines like: ## 2026-03-14 20:57:59 — OUTREACH_GENERATED
    events = []
    for m in re.finditer(r"^##\s+([^—\n]+)\s+—\s+([A-Z0-9_]+)\s*$", txt, flags=re.M):
        events.append((m.group(1).strip(), m.group(2).strip()))
    return events


def _extract_last_raw_json(txt: str, event_name: str) -> dict | None:
    """
    Extract the last RAW JSON payload for a given event by segmenting the history:
    Segment = from last header "## ... — EVENT" up to the next "## ... — ..."
    Then parse the ```json block inside that segment only.
    """
    headers = list(re.finditer(rf"^##\s+([^—\n]+)\s+—\s+{re.escape(event_name)}\s*$", txt, flags=re.M))
    if not headers:
        return None

    last = headers[-1]
    seg_start = last.start()

    next_header = re.search(r"^##\s+[^—\n]+\s+—\s+[A-Z0-9_]+\s*$", txt[last.end():], flags=re.M)
    seg_end = (last.end() + next_header.start()) if next_header else len(txt)

    segment = txt[seg_start:seg_end]

    m = re.search(r"\*\*Payload \(raw JSON\):\*\*\s*\n\s*```json\s*\n(.*?)\n```", segment, flags=re.S)
    if not m:
        return None

    raw = m.group(1).strip()
    try:
        return json.loads(raw)
    except Exception:
        return {"_raw_parse_error": True, "_raw_text": raw[:4000]}



    last = headers[-1]
    seg_start = last.start()

    # Find next header after seg_start
    next_header = re.search(r"^##\s+[^—\n]+\s+—\s+[A-Z0-9_]+\s*$", txt[last.end():], flags=re.M)
    seg_end = (last.end() + next_header.start()) if next_header else len(txt)

    segment = txt[seg_start:seg_end]

    m = re.search(r"\*\*Payload \(raw JSON\):\*\*\s*\n\s*```json\s*\n(.*?)\n```", segment, flags=re.S)
    if not m:
        return None

    raw = m.group(1).strip()
    try:
        return json.loads(raw)
    except Exception:
        return {"_raw_parse_error": True, "_raw_text": raw[:4000]}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lead-id", required=True)
    args = ap.parse_args()

    lead_id = str(args.lead_id).strip()

    df = load_pipeline()
    df["lead_id"] = df["lead_id"].astype(str)
    row_df = df[df["lead_id"] == lead_id]
    lead = row_df.iloc[0].to_dict() if not row_df.empty else {}

    hist = _read_history(lead_id)
    events = _extract_events(hist)

    last_outreach = _extract_last_raw_json(hist, "OUTREACH_GENERATED")
    last_followup = _extract_last_raw_json(hist, "FOLLOWUP_GENERATED")
    last_reply = _extract_last_raw_json(hist, "REPLY_DRAFTED")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"lead_pack_{lead_id}_{_now_tag()}.md"

    lines = []
    lines.append(f"# Lead Pack — {lead_id}\n\n")

    lines.append("## 1) Lead snapshot\n\n")
    if lead:
        keys = ["track","contact_name","company","title","location","score","priority","status","next_followup","last_action","linkedin_url"]
        for k in keys:
            if k in lead and str(lead.get(k,"")).strip():
                lines.append(f"- **{k}**: {lead.get(k)}\n")
    else:
        lines.append("_Lead introuvable dans pipeline._\n")
    lines.append("\n")

    lines.append("## 2) Timeline (events)\n\n")
    if events:
        for ts, ev in events:
            lines.append(f"- {ts} — **{ev}**\n")
    else:
        lines.append("_Aucun événement._\n")
    lines.append("\n")

    def render_block(title: str, payload: dict | None):
        lines.append(f"## {title}\n\n")
        if not payload:
            lines.append("_Aucun._\n\n")
            return
        lines.append("```json\n")
        lines.append(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
        lines.append("```\n\n")

    render_block("3) Last OUTREACH (raw)", last_outreach)
    render_block("4) Last FOLLOWUP (raw)", last_followup)
    render_block("5) Last REPLY_DRAFTED (raw)", last_reply)

    lines.append("## 6) Next-step checklist\n\n")
    lines.append("- [ ] Choisir le message à envoyer (FR/EN + variant)\n")
    lines.append("- [ ] Envoyer manuellement sur LinkedIn\n")
    lines.append("- [ ] Cliquer **Mark SENT** (ou **Mark REPLIED**) dans le cockpit\n")
    lines.append("- [ ] Vérifier les follow-ups dus chaque jour\n")
    lines.append("\n")

    out_path.write_text("".join(lines), encoding="utf-8")
    print(f"OK: {out_path}")

if __name__ == "__main__":
    main()
