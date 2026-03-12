import argparse
from datetime import date
from src.store import load_pipeline, save_pipeline, append_event

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--lead-id", required=True)
    args = p.parse_args()

    df = load_pipeline()
    lid = args.lead_id
    if lid not in set(df["lead_id"].astype(str).tolist()):
        raise SystemExit(f"Lead not found: {lid}")

    today = date.today().isoformat()
    df.loc[df["lead_id"] == lid, "status"] = "SENT"
    df.loc[df["lead_id"] == lid, "next_followup"] = today

    save_pipeline(df)
    append_event(lid, "FOLLOWUP_FORCE_TODAY", f"next_followup={today}")
    print(f"OK: {lid} next_followup forced to today={today}")

if __name__ == "__main__":
    main()
