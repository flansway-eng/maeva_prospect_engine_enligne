import argparse
from datetime import date
from src.store import load_pipeline, save_pipeline, append_event

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--lead-id", required=True)
    p.add_argument("--details", default="", help="Short note about the reply")
    args = p.parse_args()

    df = load_pipeline()
    lid = args.lead_id
    if lid not in set(df["lead_id"].astype(str).tolist()):
        raise SystemExit(f"Lead not found: {lid}")

    today = date.today().isoformat()
    df.loc[df["lead_id"] == lid, "status"] = "REPLIED"
    df.loc[df["lead_id"] == lid, "last_action"] = f"REPLIED_{today}"
    df.loc[df["lead_id"] == lid, "next_followup"] = ""

    save_pipeline(df)
    append_event(lid, "REPLIED", args.details)
    print(f"OK: {lid} marked REPLIED (followups stopped).")

if __name__ == "__main__":
    main()
