import argparse
import asyncio
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from rich import print

from src.store import load_pipeline, append_event
from src.llm_client import make_deepseek_client
from autogen_agentchat.agents import AssistantAgent
from src.followups import generate_followup

OUT_DIR = Path("out")
OUT_DIR.mkdir(exist_ok=True)

LANGS = ["FR", "EN"]
STYLES = ["POLITE", "DIRECT", "SOFT_CLOSE"]

def detect_stage(last_action: str) -> int:
    s = (last_action or "").upper()
    if s.startswith("FOLLOWUP1_"): return 2
    if s.startswith("FOLLOWUP2_"): return 3
    if s.startswith("FOLLOWUP3_"): return 3
    if s.startswith("SENT_") or s.startswith("PACK_"): return 1
    return 1

async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--top", type=int, default=20)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    load_dotenv(override=True)
    today = date.today().isoformat()

    df = load_pipeline()
    due = df[(df["status"] == "SENT") & (df["next_followup"].astype(str).str.len() > 0)]
    due = due[due["next_followup"] <= today]
    due = due.sort_values(by=["priority","score"], ascending=[True, False]).head(args.top)

    if due.empty:
        print("[yellow]No follow-ups due.[/yellow]")
        return

    out_path = OUT_DIR / f"followups_pack_{today.replace('-','')}.md"
    lines = [f"# Follow-ups due — {today}\n\n"]

    if args.dry_run:
        for _, r in due.iterrows():
            stage = detect_stage(r.get("last_action",""))
            lines.append(f"## {r['contact_name']} — {r['company']} — {r['title']} | lead_id={r['lead_id']} | stage={stage}\n")
            lines.append("- [DRY_RUN] FR/EN + 3 styles\n\n---\n")
        out_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"[bold cyan]OUTPUT[/bold cyan] {out_path}")
        return

    client = make_deepseek_client()
    agent = AssistantAgent(
        name="followup_writer",
        model_client=client,
        system_message="Tu écris des relances sobres, respectueuses, et utiles. Zéro invention.",
    )

    for _, r in due.iterrows():
        lead = r.to_dict()
        stage = detect_stage(lead.get("last_action",""))

        lines.append(f"## {lead['contact_name']} — {lead['company']} — {lead['title']} | lead_id={lead['lead_id']} | stage={stage}\n")

        for lang in LANGS:
            for style in STYLES:
                msg = await generate_followup(agent, lead, stage, lang, style)
                lines.append(f"**FOLLOWUP / {lang} / stage={stage} / {style}**\n\n{msg}\n\n")

        lines.append("\n---\n")
        append_event(lead["lead_id"], "FOLLOWUP_DRAFTED", f"stage={stage} date={today}")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[bold cyan]OUTPUT[/bold cyan] {out_path}")
    print("[bold]Next:[/bold] Maeva envoie manuellement, puis mark_followup_sent.py.")

if __name__ == "__main__":
    asyncio.run(main())
