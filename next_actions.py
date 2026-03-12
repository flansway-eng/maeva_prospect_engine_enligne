import argparse
from datetime import date
import pandas as pd
from rich import print
from src.store import load_pipeline

PRIO_ORDER = {"A": 0, "B": 1, "C": 2}

def action_for_row(row, today: str) -> str:
    status = row["status"]
    next_f = str(row.get("next_followup","")).strip()

    if status == "SENT" and next_f and next_f <= today:
        return "FOLLOWUP_DUE"
    if status == "DRAFT_READY":
        return "SEND_NOW"
    if status == "NEW":
        return "PREPARE_PACK"
    if status == "REPLIED":
        return "HANDLE_REPLY"
    return "NONE"

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--top", type=int, default=20)
    p.add_argument("--track", default="", help="Filter: MA / TS / TT (optional)")
    args = p.parse_args()

    today = date.today().isoformat()
    df = load_pipeline()

    if args.track:
        df = df[df["track"] == args.track]

    df = df.copy()
    df["action"] = df.apply(lambda r: action_for_row(r, today), axis=1)
    df = df[df["action"] != "NONE"]

    if df.empty:
        print("[yellow]No actions right now.[/yellow]")
        return

    df["prio_rank"] = df["priority"].map(lambda x: PRIO_ORDER.get(str(x), 9))
    df = df.sort_values(by=["prio_rank","score"], ascending=[True, False]).head(args.top)

    print(f"[bold cyan]=== NEXT ACTIONS (Top {len(df)}) — {today} ===[/bold cyan]")
    for _, r in df.iterrows():
        print(
            f"- [{r['action']}] {r['lead_id']} | {r['contact_name']} | {r['company']} | {r['title']} "
            f"| track={r['track']} | prio={r['priority']} | score={r['score']} | next={r.get('next_followup','')}"
        )

    # Mini synthèse
    print("\n[bold]Summary[/bold]")
    print(df["action"].value_counts().to_string())

if __name__ == "__main__":
    main()
