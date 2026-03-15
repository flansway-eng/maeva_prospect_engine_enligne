from datetime import date
import pandas as pd

PRIO_ORDER = {"A": 0, "B": 1, "C": 2}

def compute_next_actions(df: pd.DataFrame, top_k: int = 20, track: str | None = None) -> pd.DataFrame:
    """
    Retourne un dataframe d'actions priorisées.
    Actions:
    - FOLLOWUP_DUE: status=SENT & next_followup <= today
    - SEND_NOW: status=DRAFT_READY
    - PREPARE_PACK: status=NEW
    - HANDLE_REPLY: status=REPLIED
    """
    today = date.today().isoformat()
    x = df.copy()

    if track and track != "ALL":
        x = x[x["track"] == track]

    x["next_followup"] = x["next_followup"].astype(str)
    x["action"] = "NONE"

    due = (x["status"] == "SENT") & (x["next_followup"].str.len() > 0) & (x["next_followup"] <= today)
    x.loc[due, "action"] = "FOLLOWUP_DUE"

    x.loc[x["status"] == "DRAFT_READY", "action"] = x.loc[x["status"] == "DRAFT_READY", "action"].replace("NONE", "SEND_NOW")
    x.loc[x["status"] == "NEW", "action"] = x.loc[x["status"] == "NEW", "action"].replace("NONE", "PREPARE_PACK")
    x.loc[x["status"] == "REPLIED", "action"] = x.loc[x["status"] == "REPLIED", "action"].replace("NONE", "HANDLE_REPLY")

    x = x[x["action"] != "NONE"]
    if x.empty:
        return x

    x["prio_rank"] = x["priority"].map(lambda v: PRIO_ORDER.get(str(v), 9))
    x = x.sort_values(by=["prio_rank", "score"], ascending=[True, False]).head(top_k)

    cols = ["action","lead_id","contact_name","company","title","track","priority","score","next_followup","status"]
    return x[cols]
