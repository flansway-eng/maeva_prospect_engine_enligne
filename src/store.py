import hashlib
from datetime import date
from pathlib import Path
import pandas as pd
from typing import Tuple
from .schemas import Lead, PipelineRow

DATA_DIR = Path("data")
PIPELINE_PATH = DATA_DIR / "pipeline.csv"
EVENTS_PATH = DATA_DIR / "events.csv"


def _lead_id(lead: Lead) -> str:
    raw = f"{lead.track}|{lead.company}|{lead.contact_name}|{lead.title}|{lead.linkedin_url}".lower().strip()
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def init_storage() -> None:
    DATA_DIR.mkdir(exist_ok=True)

    if not PIPELINE_PATH.exists():
        pd.DataFrame(columns=[
            "lead_id","track","company","contact_name","title","linkedin_url","location","source","notes",
            "score","priority","status","last_action","next_followup"
        ]).to_csv(PIPELINE_PATH, index=False)

    if not EVENTS_PATH.exists():
        pd.DataFrame(columns=["date","lead_id","event","details"]).to_csv(EVENTS_PATH, index=False)


def load_pipeline() -> pd.DataFrame:
    init_storage()
    df = pd.read_csv(
        PIPELINE_PATH,
        dtype={
            "lead_id": "string",
            "track": "string",
            "company": "string",
            "contact_name": "string",
            "title": "string",
            "linkedin_url": "string",
            "location": "string",
            "source": "string",
            "notes": "string",
            "priority": "string",
            "status": "string",
            "last_action": "string",
            "next_followup": "string",
        },
        keep_default_na=False,
    )

    # score: force int
    if "score" not in df.columns:
        df["score"] = 0
    df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0).astype(int)

    # Colonnes obligatoires si manquantes
    for col in ["priority", "status", "last_action", "next_followup", "notes"]:
        if col not in df.columns:
            df[col] = ""

    return df

def save_pipeline(df: pd.DataFrame) -> None:
    df.to_csv(PIPELINE_PATH, index=False)


def append_event(lead_id: str, event: str, details: str = "") -> None:
    init_storage()
    df = pd.read_csv(EVENTS_PATH)
    df.loc[len(df)] = [date.today().isoformat(), lead_id, event, details]
    df.to_csv(EVENTS_PATH, index=False)


def ingest_leads_csv(path: str) -> Tuple[pd.DataFrame, int]:
    """
    Ingest manuel: merge dans pipeline sur lead_id.
    Retourne (pipeline_df, nb_nouveaux).
    """
    init_storage()
    pipeline = load_pipeline()
    inbox = pd.read_csv(path)

    required = {"track","company","contact_name","title","linkedin_url","location","source","notes"}
    missing = required - set(inbox.columns)
    if missing:
        raise ValueError(f"Missing columns in input CSV: {sorted(missing)}")

    new_rows = []
    existing_ids = set(pipeline["lead_id"].astype(str).tolist()) if len(pipeline) else set()

    for _, r in inbox.iterrows():
        lead = Lead(**{k: r[k] for k in required})
        lid = _lead_id(lead)
        if lid in existing_ids:
            continue

        row = PipelineRow(**lead.model_dump(), lead_id=lid).model_dump()
        new_rows.append(row)
        append_event(lid, "INGESTED", f"source={lead.source}")

    if new_rows:
        pipeline = pd.concat([pipeline, pd.DataFrame(new_rows)], ignore_index=True)
        save_pipeline(pipeline)

    return pipeline, len(new_rows)
