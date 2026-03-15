from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import argparse
import glob
import pandas as pd

from src.store import load_pipeline
from src.actions import compute_next_actions

OUT = Path("out")
OUT.mkdir(exist_ok=True)

EVENTS_PATH = Path("data/events.csv")


def latest_file(pattern: str) -> str | None:
    files = sorted(glob.glob(pattern))
    return files[-1] if files else None


def followup_stage_for_lead(lead_id: str) -> int:
    """
    Détermine un stage de follow-up à partir de data/events.csv si disponible.
    Heuristique robuste (pas d'hypothèse sur le schéma exact d'events):
    - compte les événements dont le champ event contient "followup" ou commence par "f" + chiffre.
    - stage = min(count+1, 3)
    Si events absents/incomplets => 1
    """
    if not EVENTS_PATH.exists():
        return 1
    try:
        ev = pd.read_csv(EVENTS_PATH)
        if "lead_id" not in ev.columns:
            return 1
        # trouver la colonne event
        event_col = "event" if "event" in ev.columns else None
        if event_col is None:
            return 1

        rows = ev[ev["lead_id"].astype(str) == str(lead_id)]
        if rows.empty:
            return 1

        def is_followup_event(x: str) -> bool:
            t = str(x).strip().lower()
            if "followup" in t:
                return True
            # f1 / f2 / f3 / f1_sent / f2_due etc.
            if t.startswith("f") and len(t) >= 2 and t[1].isdigit():
                return True
            return False

        c = sum(is_followup_event(x) for x in rows[event_col].tolist())
        return min(c + 1, 3) if c >= 0 else 1
    except Exception:
        return 1


def md_table(df: pd.DataFrame, cols: list[str]) -> str:
    if df.empty:
        return "_(aucune ligne)_\n"
    out = []
    out.append("| " + " | ".join(cols) + " |")
    out.append("| " + " | ".join(["---"] * len(cols)) + " |")
    for _, r in df.iterrows():
        out.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--track", default="ALL", help="ALL | MA | TS | TT")
    args = ap.parse_args()

    today = date.today().isoformat()

    pipeline = load_pipeline()
    actions = compute_next_actions(pipeline, top_k=int(args.top), track=args.track)

    outreach_pack = latest_file("out/outreach_pack_week_*.md")
    followups_pack = latest_file("out/followups_pack_*.md")

    # Résumé actions
    summary = actions["action"].value_counts().to_dict() if not actions.empty else {}

    lines: list[str] = []
    lines.append(f"# Daily Plan — {today}")
    lines.append("")
    lines.append("## Context")
    lines.append("- Mode: human-in-the-loop (Maeva envoie manuellement sur LinkedIn/RS).")
    lines.append(f"- Track filter: **{args.track}** | Top: **{args.top}**")
    lines.append("")
    lines.append("## Packs disponibles")
    lines.append(f"- Outreach pack: {outreach_pack or '_absent_'}")
    lines.append(f"- Followups pack: {followups_pack or '_absent_'}")
    lines.append("")
    lines.append("## Résumé (Top actions)")
    if summary:
        for k, v in summary.items():
            lines.append(f"- **{k}**: {v}")
    else:
        lines.append("Aucune action détectée.")
    lines.append("")

    lines.append("## Tableau — Next Actions")
    cols = ["action", "lead_id", "contact_name", "company", "title", "track", "priority", "score", "next_followup", "status"]
    lines.append(md_table(actions, cols))

    # Détails par lead
    lines.append("## Détails opérationnels (quoi faire maintenant)")
    if actions.empty:
        lines.append("_Rien à exécuter aujourd'hui._")
    else:
        # index pipeline pour récupérer linkedin_url / notes
        pip = pipeline.copy()
        pip["lead_id"] = pip["lead_id"].astype(str)
        pip_idx = pip.set_index("lead_id")

        for _, r in actions.iterrows():
            lid = str(r["lead_id"])
            action = str(r["action"])
            contact = str(r.get("contact_name", ""))
            company = str(r.get("company", ""))
            title = str(r.get("title", ""))
            track = str(r.get("track", ""))
            prio = str(r.get("priority", ""))
            score = str(r.get("score", ""))
            status = str(r.get("status", ""))
            next_f = str(r.get("next_followup", ""))

            linkedin_url = ""
            notes = ""
            if lid in pip_idx.index:
                linkedin_url = str(pip_idx.loc[lid].get("linkedin_url", "") or "")
                notes = str(pip_idx.loc[lid].get("notes", "") or "")

            lines.append("")
            lines.append(f"### {contact} — {company} ({track})  \n`lead_id={lid}` | prio={prio} | score={score} | status={status}")
            if linkedin_url:
                lines.append(f"- LinkedIn: {linkedin_url}")
            if notes:
                lines.append(f"- Notes: {notes}")

            if action == "SEND_NOW":
                lines.append("**Action recommandée :** Envoyer un message d’approche (Outreach).")
                lines.append("- UI → `Packs & Follow-ups` → `Generate Outreach Pack` (ou ouvrir le pack existant).")
                lines.append(f"- Pack: {outreach_pack or '⚠️ aucun pack trouvé (génère-le)'}")
                lines.append("- Ensuite : UI → `Pipeline/Quick Actions` → `Mark SENT (J+3)` (planifie la relance).")

            elif action == "FOLLOWUP_DUE":
                stage = followup_stage_for_lead(lid)
                lines.append("**Action recommandée :** Relance due aujourd’hui.")
                lines.append("- UI → `Packs & Follow-ups` → `Generate Followups Pack` (si nécessaire).")
                lines.append(f"- Pack: {followups_pack or '⚠️ aucun pack trouvé (génère-le)'}")
                lines.append(f"- Stage suggéré (d’après events si disponibles) : **{stage}**")
                lines.append("- UI → `Pipeline/Quick Actions` → `Mark FOLLOWUP SENT` (avec le stage).")

            elif action == "HANDLE_REPLY":
                lines.append("**Action recommandée :** Traiter la réponse.")
                lines.append("- Lire le message LinkedIn et qualifier : intérêt / refus / demande d’info / proposition d’appel.")
                lines.append("- UI → `Pipeline editor` → passer `status` à `CALL` ou `INTERVIEW` si applicable.")
                lines.append("- Ajouter note + prochaine action (date).")

            elif action == "PREPARE_PACK":
                lines.append("**Action recommandée :** Préparer un pack (lead NEW).")
                lines.append("- UI → `Inbox Import` → ingest si besoin.")
                lines.append("- UI → `Packs & Follow-ups` → Generate Outreach Pack, puis Mark SENT.")

            else:
                lines.append("**Action recommandée :** Vérifier le lead dans le pipeline.")

    out_path = OUT / f"daily_plan_{today.replace('-','')}.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"OK: {out_path}")

if __name__ == "__main__":
    main()
