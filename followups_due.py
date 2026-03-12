from datetime import date
from src.store import load_pipeline

def main():
    today = date.today().isoformat()
    df = load_pipeline()

    # due si next_followup non vide et <= today
    df = df[(df["status"] == "SENT") & (df["next_followup"].astype(str).str.len() > 0)]
    due = df[df["next_followup"] <= today]

    if due.empty:
        print("No follow-ups due today.")
        return

    print("=== FOLLOW-UPS DUE (<= today) ===")
    for _, r in due.sort_values(by=["priority","score"], ascending=[True, False]).iterrows():
        print(f"- {r['lead_id']} | {r['contact_name']} | {r['company']} | {r['title']} | track={r['track']} | prio={r['priority']} | score={r['score']} | next={r['next_followup']}")

if __name__ == "__main__":
    main()
