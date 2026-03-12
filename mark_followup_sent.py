import argparse
from datetime import date, timedelta
from src.store import load_pipeline, save_pipeline, append_event

def next_delta(stage: int) -> int:
    if stage == 1: return 4   # J+3 -> J+7
    if stage == 2: return 7   # J+7 -> J+14
    return 0                  # stage 3 -> close

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--lead-id", required=True)
    p.add_argument("--stage", type=int, required=True, choices=[1,2,3])
    args = p.parse_args()

    df = load_pipeline()
    lid = args.lead_id
    stage = args.stage

    if lid not in set(df["lead_id"].astype(str).tolist()):
        raise SystemExit(f"Lead not found: {lid}")

    today = date.today().isoformat()

    if stage in (1,2):
        next_date = (date.today() + timedelta(days=next_delta(stage))).isoformat()
        df.loc[df["lead_id"] == lid, "status"] = "SENT"
        df.loc[df["lead_id"] == lid, "last_action"] = f"FOLLOWUP{stage}_SENT_{today}"
        df.loc[df["lead_id"] == lid, "next_followup"] = next_date
        append_event(lid, f"FOLLOWUP{stage}_SENT", f"next_followup={next_date}")
        save_pipeline(df)
        print(f"OK: {lid} FOLLOWUP{stage} sent, next_followup={next_date}")
        return

    # stage 3 = dernière relance -> close
    df.loc[df["lead_id"] == lid, "status"] = "CLOSED"
    df.loc[df["lead_id"] == lid, "last_action"] = f"FOLLOWUP3_SENT_{today}"
    df.loc[df["lead_id"] == lid, "next_followup"] = ""
    append_event(lid, "FOLLOWUP3_SENT", "closed_after_last_followup")
    save_pipeline(df)
    print(f"OK: {lid} FOLLOWUP3 sent, status=CLOSED")

if __name__ == "__main__":
    main()
