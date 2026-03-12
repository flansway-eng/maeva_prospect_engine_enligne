import argparse
import asyncio
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
import pandas as pd
from rich import print

from src.llm_client import make_deepseek_client
from autogen_agentchat.agents import AssistantAgent

from src.store import ingest_leads_csv, load_pipeline, save_pipeline, append_event
from src.scoring import apply_scoring
from src.messages import generate_message

OUT_DIR = Path("out")
OUT_DIR.mkdir(exist_ok=True)

PERSONAS = ["DECIDER", "RELAY", "PEER"]
LANGS = ["FR", "EN"]
VARIANTS = ["ULTRA", "STANDARD", "WARM"]


def extract_top(df: pd.DataFrame, top_k: int) -> pd.DataFrame:
    df = df.copy()
    df = df[df["status"].isin(["NEW", "DRAFT_READY"])]
    df = df.sort_values(by=["priority", "score"], ascending=[True, False])  # A then B then C
    return df.head(top_k)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="CSV leads inbox (manual export)")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_dotenv(override=True)

    # 1) Ingest
    _, n_new = ingest_leads_csv(args.input)
    print(f"[bold green]INGEST[/bold green] new_leads={n_new}")

    # 2) Scoring
    pipeline = load_pipeline()
    pipeline = apply_scoring(pipeline)

    # 3) Top K
    top_df = extract_top(pipeline, args.top)
    if top_df.empty:
        print("[yellow]No leads to process (NEW/DRAFT_READY).[/yellow]")
        save_pipeline(pipeline)
        return

    week = date.today().strftime("%Y%m%d")
    out_path = OUT_DIR / f"outreach_pack_week_{week}.md"

    messages = []
    if args.dry_run:
        for _, row in top_df.iterrows():
            messages.append(f"### {row['contact_name']} — {row['company']} — {row['title']} (track={row['track']})\n")
            messages.append("- [DRY_RUN] Messages ULTRA/STANDARD/WARM à générer\n\n---\n")
        out_path.write_text("\n".join(messages), encoding="utf-8")
        save_pipeline(pipeline)
        print(f"[bold cyan]OUTPUT[/bold cyan] {out_path}")
        return

    client = make_deepseek_client()
    copywriter = AssistantAgent(
        name="copywriter",
        model_client=client,
        system_message="Tu es un copywriter RH. Sobre, professionnel, zéro invention.",
    )

    for _, row in top_df.iterrows():
        lead = row.to_dict()
        header = f"### {lead['contact_name']} — {lead['company']} — {lead['title']} | track={lead['track']} | score={lead['score']} | prio={lead['priority']}\n"
        messages.append(header)

        for persona in PERSONAS:
            for lang in LANGS:
                for variant in VARIANTS:
                    msg = await generate_message(copywriter, lead, persona, lang, variant)
                    messages.append(f"**{persona} / {lang} / {variant}**\n\n{msg}\n\n")

        messages.append("\n---\n")

        lid = lead["lead_id"]
        pipeline.loc[pipeline["lead_id"] == lid, "status"] = "DRAFT_READY"
        pipeline.loc[pipeline["lead_id"] == lid, "last_action"] = f"PACK_{week}"
        append_event(lid, "PACK_CREATED", f"week={week}")

    out_path.write_text("\n".join(messages), encoding="utf-8")
    save_pipeline(pipeline)

    print(f"[bold cyan]OUTPUT[/bold cyan] {out_path}")
    print("[bold]Next:[/bold] Maeva envoie manuellement sur LinkedIn (human-in-the-loop).")


if __name__ == "__main__":
    asyncio.run(main())
