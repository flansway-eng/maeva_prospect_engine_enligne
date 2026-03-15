from datetime import date
from pathlib import Path
import pandas as pd

from src.store import load_pipeline
from src.actions import compute_next_actions

OUT = Path("out")
OUT.mkdir(exist_ok=True)

def main():
    today = date.today().isoformat()
    df = load_pipeline()

    # Sheets
    pipeline = df.sort_values(by=["priority","score"], ascending=[True, False])
    next_actions = compute_next_actions(df, top_k=50, track="ALL")

    # Scorecard simple
    scorecard = (
        df.groupby(["track","status"])
          .size()
          .reset_index(name="count")
          .sort_values(by=["track","status"])
    )

    out_path = OUT / f"maeva_pack_{today}.xlsx"
    with pd.ExcelWriter(out_path, engine="openpyxl") as w:
        pipeline.to_excel(w, sheet_name="pipeline", index=False)
        next_actions.to_excel(w, sheet_name="next_actions", index=False)
        scorecard.to_excel(w, sheet_name="scorecard", index=False)

    print(f"OK: {out_path}")

if __name__ == "__main__":
    main()
