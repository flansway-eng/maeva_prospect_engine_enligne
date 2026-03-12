import argparse
from datetime import date, timedelta
from src.store import load_pipeline, save_pipeline, append_event

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--lead-id", required=True)
    p.add_argument("--days", type=int, default=3, help="Next follow-up in N days (default 3)")
    args = p.parse_args()

    df = load_pipeline()
    lid = args.lead_id

    if lid not in set(df["lead_id"].astype(str).tolist()):
        raise SystemExit(f"Lead not found: {lid}")

    next_date = (date.today() + timedelta(days=args.days)).isoformat()

    df.loc[df["lead_id"] == lid, "status"] = "SENT"
    df.loc[df["lead_id"] == lid, "last_action"] = f"SENT_{date.today().isoformat()}"
    df.loc[df["lead_id"] == lid, "next_followup"] = next_date

    save_pipeline(df)
    append_event(lid, "SENT", f"next_followup={next_date}")

    print(f"OK: {lid} marked SENT, next_followup={next_date}")

if __name__ == "__main__":
    main()
