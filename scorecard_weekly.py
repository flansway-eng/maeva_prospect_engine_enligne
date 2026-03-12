import pandas as pd
from datetime import date, timedelta
from pathlib import Path

from src.store import load_pipeline

EVENTS_PATH = Path("data/events.csv")

def main():
    df = load_pipeline()

    print("=== PIPELINE SNAPSHOT ===")
    print(df.groupby(["track","status"]).size().to_string())
    print("\n=== PRIORITIES ===")
    print(df.groupby(["priority"]).size().to_string())

    if not EVENTS_PATH.exists():
        print("\nNo events.csv yet.")
        return

    ev = pd.read_csv(EVENTS_PATH)
    since = (date.today() - timedelta(days=7)).isoformat()
    ev7 = ev[ev["date"] >= since]

    print(f"\n=== EVENTS (last 7 days since {since}) ===")
    print(ev7.groupby(["event"]).size().sort_values(ascending=False).to_string())

    # mini KPI action
    sent = int((ev7["event"] == "SENT").sum())
    f1 = int((ev7["event"] == "FOLLOWUP1_SENT").sum())
    f2 = int((ev7["event"] == "FOLLOWUP2_SENT").sum())
    f3 = int((ev7["event"] == "FOLLOWUP3_SENT").sum())
    rep = int((ev7["event"] == "REPLIED").sum())

    print("\n=== KPI (last 7 days) ===")
    print(f"SENT={sent} | F1={f1} | F2={f2} | F3={f3} | REPLIED={rep}")

if __name__ == "__main__":
    main()
