import os
from datetime import date
from pathlib import Path
import pandas as pd
import streamlit as st

# --- Cloud bootstrap (ensure folders exist) ---
from pathlib import Path
for d in ["data", "data/inbox", "data/conversations", "out"]:
    Path(d).mkdir(parents=True, exist_ok=True)
# --------------------------------------------


# --- Cloud bootstrap (ensure folders exist) ---
from pathlib import Path
for d in ["data", "data/inbox", "data/conversations", "out"]:
    Path(d).mkdir(parents=True, exist_ok=True)
# --------------------------------------------

from src.conversation_log import log_event
from src.ui_messages import generate_outreach_trackaware, generate_reply_handler_json


from src.store import ingest_leads_csv, load_pipeline, save_pipeline, append_event_bulk
from src.scoring import apply_scoring
from src.actions import compute_next_actions
from src.ui_messages import generate_outreach_trackaware, generate_outreach_json, generate_followup_json, guess_followup_stage

# Actions existantes (scripts) réutilisables
import subprocess

APP_TITLE = "Maeva Prospect Engine — Streamlit Cockpit"
OUT_DIR = Path("out")
OUT_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)
st.caption("Copilote de prospection (M&A / TS / TT) — human-in-the-loop, sans automatisation LinkedIn.")


# ---------- Helpers ----------
def run_cmd(cmd: list[str]) -> tuple[int, str]:
    """Run command and return (code, output)."""
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
    return p.returncode, out.strip()

def refresh_pipeline() -> pd.DataFrame:
    """
    Recalcule le score sans écraser les champs CRM saisis par Maeva.
    Champs protégés: status, priority, next_followup, notes, last_action
    """
    df = load_pipeline()

    protected = ["lead_id", "status", "priority", "next_followup", "notes", "last_action"]
    keep = df[[c for c in protected if c in df.columns]].copy()

    df2 = apply_scoring(df)

    if "lead_id" in df2.columns and "lead_id" in keep.columns:
        df2 = df2.merge(keep, on="lead_id", how="left", suffixes=("", "_keep"))
        for col in protected[1:]:
            k = f"{col}_keep"
            if k in df2.columns:
                base = df2[col] if col in df2.columns else ""
                kept = df2[k]
                # si valeur CRM non vide => priorité au CRM
                df2[col] = kept.where(kept.astype(str).str.len() > 0, base)
                df2.drop(columns=[k], inplace=True)

    save_pipeline(df2)
    return df2
def df_download_button(df: pd.DataFrame, filename: str, label: str):
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(label, csv, file_name=filename, mime="text/csv")


# ---------- Sidebar ----------
st.sidebar.header("Configuration")
env_ok = bool(os.getenv("DEEPSEEK_API_KEY"))
st.sidebar.write("DeepSeek key:", "✅" if env_ok else "❌ (lancer avec: `uv run --env-file .env streamlit run app.py`)")

track_filter = st.sidebar.selectbox("Track", ["ALL", "MA", "TS", "TT"], index=0)
status_filter = st.sidebar.multiselect(
    "Status",
    ["NEW", "DRAFT_READY", "SENT", "REPLIED", "CALL", "INTERVIEW", "CLOSED"],
    default=["NEW", "DRAFT_READY", "SENT"]
)
prio_filter = st.sidebar.multiselect("Priority", ["A", "B", "C"], default=["A", "B", "C"])

top_k = st.sidebar.number_input("Top K (packs & next actions)", min_value=1, max_value=100, value=20, step=1)

st.sidebar.divider()
st.sidebar.subheader("Fichiers")
st.sidebar.write("Pipeline:", "data/pipeline.csv")
st.sidebar.write("Events:", "data/events.csv")
st.sidebar.write("Output:", "out/")


# ---------- Tabs ----------
tab1, tab2, tab3, tab4 = st.tabs(["Inbox Import", "Pipeline", "Next Actions", "Packs & Follow-ups"])


# ---------- Tab 1: Inbox Import ----------
with tab1:
    st.subheader("1) Importer des leads (CSV)")

    uploaded = st.file_uploader("Upload CSV leads (colonnes: track,company,contact_name,title,linkedin_url,location,source,notes)", type=["csv"])
    colA, colB = st.columns([1, 1])

    if uploaded is not None:
        tmp_path = Path("data") / "inbox_uploaded.csv"
        tmp_path.parent.mkdir(exist_ok=True)
        tmp_path.write_bytes(uploaded.getbuffer())

        with colA:
            st.write("Aperçu du fichier importé")
            inbox_df = pd.read_csv(tmp_path)
            st.dataframe(inbox_df, width='stretch', height=280)

        with colB:
            if st.button("Ingest → pipeline", type="primary"):
                try:
                    pipeline_df, n_new = ingest_leads_csv(str(tmp_path))
                    st.success(f"Ingest terminé. Nouveaux leads ajoutés: {n_new}")
                except Exception as e:
                    st.error(str(e))

    st.info("Conformité: pas de scraping. Maeva collecte manuellement les URLs/profils et les importe ici.")


# ---------- Tab 2: Pipeline ----------
with tab2:
    st.subheader("2) Pipeline (filtrer, trier, exporter)")
    df = refresh_pipeline()

    # Filters
    view = df.copy()
    if track_filter != "ALL":
        view = view[view["track"] == track_filter]
    view = view[view["status"].isin(status_filter)]
    view = view[view["priority"].isin(prio_filter)]

    view = view.sort_values(by=["priority", "score"], ascending=[True, False])

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        # Édition inline (mini-CRM)
        editable_cols = ["status", "priority", "next_followup", "notes"]
        base_cols = ["lead_id", "track", "contact_name", "company", "title", "score"]
        show_cols = base_cols + editable_cols + ["last_action"]

        view2 = view.copy()
        # Assure présence des colonnes
        for c in show_cols:
            if c not in view2.columns:
                view2[c] = ""

        editor = st.data_editor(
            view2[show_cols],
            width="stretch",
            height=520,
            num_rows="fixed",
            key="pipeline_editor",
            column_config={
                "status": st.column_config.SelectboxColumn(
                    "status",
                    options=["NEW","DRAFT_READY","SENT","REPLIED","CALL","INTERVIEW","CLOSED"],
                    required=True,
                ),
                "priority": st.column_config.SelectboxColumn(
                    "priority",
                    options=["A","B","C"],
                    required=True,
                ),
                "next_followup": st.column_config.TextColumn("next_followup (YYYY-MM-DD)"),
                "notes": st.column_config.TextColumn("notes"),
            },
        )

        csave1, csave2 = st.columns([1, 2])
        with csave1:
            save_clicked = st.button("Save changes", type="primary")
        with csave2:
            st.caption("Seules les colonnes status/priority/next_followup/notes sont prises en compte. "
                       "Les autres champs ne sont pas modifiés.")

        if save_clicked:
            # Recharger pipeline complet, puis appliquer les changements sur lead_id
            full = load_pipeline()
            full = apply_scoring(full)  # garde score cohérent
            changed_events = []

            # indexer editor par lead_id
            ed = editor.copy()
            ed["lead_id"] = ed["lead_id"].astype(str)

            full["lead_id"] = full["lead_id"].astype(str)
            full_idx = full.set_index("lead_id")

            for _, r in ed.iterrows():
                lid = str(r["lead_id"])
                if lid not in full_idx.index:
                    continue

                # champs éditables
                for col in ["status","priority","next_followup","notes"]:
                    newv = "" if r.get(col) is None else str(r.get(col))
                    oldv = "" if full_idx.loc[lid].get(col) is None else str(full_idx.loc[lid].get(col))
                    if newv != oldv:
                        full_idx.at[lid, col] = newv
                        changed_events.append((lid, "UI_EDIT", f"{col}: '{oldv}' -> '{newv}'"))

            full = full_idx.reset_index()
            
            # Validation stricte next_followup: YYYY-MM-DD ou vide
            import re as _re
            invalid = []
            for _, rr in ed.iterrows():
                v = "" if rr.get("next_followup") is None else str(rr.get("next_followup")).strip()
                if v and not _re.match(r"^\d{4}-\d{2}-\d{2}$", v):
                    invalid.append((str(rr.get("lead_id","")), v))
            if invalid:
                st.error("Save refusé: next_followup doit être au format YYYY-MM-DD (ex: 2026-03-14).")
                st.write("Valeurs invalides:")
                st.dataframe(invalid, width="stretch")
                st.stop()

            save_pipeline(full)

            # events (si dispo)
            try:
                if changed_events and "append_event_bulk" in globals():
                    append_event_bulk(changed_events)
            except Exception:
                pass

            st.success(f"Saved. {len(changed_events)} change(s) applied.")
            st.rerun()


        # ---- Quick Actions (par ligne) ----
        st.markdown("---")
        st.subheader("Quick Actions (par ligne)")

        max_rows = st.slider(
            "Nombre de leads pour actions rapides",
            min_value=1,
            max_value=min(30, int(len(view))) if len(view) else 1,
            value=min(10, int(len(view))) if len(view) else 1,
            step=1,
            key="tab2_qa_limit",
        )

        qa = view.head(int(max_rows)).copy()
        if qa.empty:
            st.info("Aucun lead dans la vue filtrée.")
        else:
            for _, r in qa.iterrows():
                lid = str(r["lead_id"])
                title = f"{r['contact_name']} — {r['company']} | {r['title']} | {r['track']} | {r['status']} | prio={r['priority']} | score={r['score']}"
                with st.expander(title, expanded=False):
                    c1, c2, c3, c4 = st.columns([1,1,1,1])

                    with c1:
                        if st.button("Mark SENT (J+3)", key=f"tab2_qa_sent_{lid}"):
                            code, out = run_cmd(["uv","run","python","mark_sent.py","--lead-id", lid])
                            st.code(out, language="text")

                    with c2:
                        if st.button("Force followup TODAY", key=f"tab2_qa_force_{lid}"):
                            code, out = run_cmd(["uv","run","python","set_followup_today.py","--lead-id", lid])
                            st.code(out, language="text")

                    with c3:
                        if st.button("Mark REPLIED", key=f"tab2_qa_replied_{lid}"):
                            code, out = run_cmd(["uv","run","python","mark_replied.py","--lead-id", lid, "--details", "Reply via Pipeline quick actions"])
                            st.code(out, language="text")

                    with c4:
                        stage = st.selectbox("Stage", [1,2,3], index=0, key=f"tab2_qa_stage_{lid}")
                        if st.button("Mark FOLLOWUP SENT", key=f"tab2_qa_fup_{lid}"):
                            code, out = run_cmd(["uv","run","python","mark_followup_sent.py","--lead-id", lid, "--stage", str(stage)])
                            st.code(out, language="text")


        st.markdown("### Batch actions (multi-leads)")

        lead_labels = [
            f'{r["lead_id"]} | {r["contact_name"]} | {r["company"]} | {r["title"]} | {r["track"]} | {r["status"]} | prio={r["priority"]} | score={r["score"]}'
            for _, r in view.iterrows()
        ]
        label_to_id = {lbl: lbl.split(" | ", 1)[0].strip() for lbl in lead_labels}

        selected = st.multiselect(
            "Sélectionner des leads (dans la vue filtrée)",
            lead_labels,
            default=[],
            key="batch_select_leads"
        )
        selected_ids = [label_to_id[x] for x in selected]

        action = st.selectbox(
            "Action batch",
            ["SET_STATUS", "SET_PRIORITY", "PLAN_FOLLOWUP_PLUS_DAYS", "MARK_SENT_J3"],
            index=0,
            key="batch_action"
        )

        colB1, colB2, colB3 = st.columns([1,1,1])

        with colB1:
            new_status = st.selectbox(
                "New status",
                ["NEW","DRAFT_READY","SENT","REPLIED","CALL","INTERVIEW","CLOSED"],
                index=2,
                key="batch_new_status"
            )

        with colB2:
            new_prio = st.selectbox("New priority", ["A","B","C"], index=1, key="batch_new_prio")

        with colB3:
            days = st.number_input("Followup +N days", min_value=0, max_value=60, value=3, step=1, key="batch_days")

        if st.button("Apply batch", type="primary", key="batch_apply"):
            if not selected_ids:
                st.warning("Aucun lead sélectionné.")
            else:
                full = load_pipeline()
                full["lead_id"] = full["lead_id"].astype(str)
                idx = full.set_index("lead_id")

                from datetime import date, timedelta
                today = date.today()

                changes = 0
                for lid in selected_ids:
                    if lid not in idx.index:
                        continue

                    if action == "SET_STATUS":
                        idx.at[lid, "status"] = new_status
                        changes += 1

                    elif action == "SET_PRIORITY":
                        idx.at[lid, "priority"] = new_prio
                        changes += 1

                    elif action == "PLAN_FOLLOWUP_PLUS_DAYS":
                        idx.at[lid, "next_followup"] = (today + timedelta(days=int(days))).isoformat()
                        idx.at[lid, "status"] = "SENT"  # followup planning implies sent
                        changes += 1

                    elif action == "MARK_SENT_J3":
                        # On appelle le script pour respecter la logique existante (planifie J+3)
                        code, out = run_cmd(["uv","run","python","mark_sent.py","--lead-id", lid])
                        st.code(out, language="text")
                        changes += 1

                full2 = idx.reset_index()
                save_pipeline(full2)

                st.success(f"Batch applied: {changes} lead(s) updated.")
                st.rerun()


with tab3:
    st.subheader("3) Next Actions (Top priorités)")

    # Export Excel (pipeline + next_actions + scorecard)
    if st.button("Export Excel pack", key="export_excel_pack_btn"):
        code, out_txt = run_cmd(["uv","run","python","export_excel_pack.py"])
        st.code(out_txt, language="text")
        import glob
        files = sorted(glob.glob("out/maeva_pack_*.xlsx"))
        if files:
            latest = files[-1]
            data = Path(latest).read_bytes()
            st.download_button("Download latest Excel pack", data, file_name=Path(latest).name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.markdown("---")
    if st.button("Generate Daily Plan (Top K)", key="gen_daily_plan_btn"):
        cmd = ["uv","run","python","daily_plan.py","--top", str(top_k), "--track", (track_filter if track_filter else "ALL")]
        code, out = run_cmd(cmd)
        st.code(out, language="text")

    # Affiche + download le dernier daily plan
    import glob
    plans = sorted(glob.glob("out/daily_plan_*.md"))
    if plans:
        latest_plan = plans[-1]
        with st.expander(f"Latest Daily Plan: {Path(latest_plan).name}", expanded=False):
            txt = Path(latest_plan).read_text(encoding="utf-8", errors="replace")
            st.text(txt[:8000])
            st.download_button(
                "Download Daily Plan (.md)",
                txt.encode("utf-8"),
                file_name=Path(latest_plan).name,
                mime="text/markdown"
            )

        code, out = run_cmd(["uv","run","python","export_excel_pack.py"])
        st.code(out, language="text")
        # essaie de détecter le fichier créé
        import glob
        files = sorted(glob.glob("out/maeva_pack_*.xlsx"))
        if files:
            latest = files[-1]
            data = Path(latest).read_bytes()
            st.download_button("Download latest Excel pack", data, file_name=Path(latest).name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


    df = refresh_pipeline()
    actions_df = compute_next_actions(df, top_k=int(top_k), track=(track_filter if track_filter != "ALL" else "ALL"))

    if actions_df.empty:
        st.info("Aucune action à exécuter maintenant.")
    else:
        st.write("Clique sur **Select** pour charger le lead, puis exécute une action rapide.")
        # Table
        st.dataframe(actions_df, width="stretch", height=420)

        # Select line: simple dropdown + sync
        options = [
            f'{r.lead_id} | {r.action} | {r.contact_name} | {r.company} | {r.title}'
            for r in actions_df.itertuples(index=False)
        ]
        pick = st.selectbox("Select a lead from Next Actions", options, index=0, key="next_actions_picker")
        selected_lead_id = pick.split(" | ", 1)[0].strip()
        st.session_state["selected_lead_id"] = selected_lead_id
        st.success(f"Selected lead_id: {selected_lead_id}")

        st.markdown("### Sprint 3.8 — History (data/conversations)")
        st.markdown("---")
        st.subheader("History (conversation timeline)")
        from pathlib import Path
        import re
        hist_dir = Path("data/conversations")
        hist_path = hist_dir / f"{selected_lead_id}.md"
        colH1, colH2 = st.columns([1,1])
        with colH1:
            if st.button("Refresh history", key=f"hist_refresh_{selected_lead_id}"):
                st.rerun()
        with colH2:
            st.caption(f"File: {hist_path}")

        if not hist_dir.exists():
            st.info("Aucun dossier data/conversations pour le moment. Il sera créé automatiquement au premier log_event().")
        elif not hist_path.exists():
            st.info("Aucune conversation enregistrée pour ce lead (pas encore d’événements loggés).")
        else:
            txt = hist_path.read_text(encoding="utf-8", errors="replace")
            # Parse events: lines like '## 2026-03-14 20:57:59 — OUTREACH_GENERATED'
            events = []
            for m in re.finditer(r"^##\s+([^—\n]+)\s+—\s+([A-Z0-9_]+)\s*$", txt, flags=re.M):
                ts = m.group(1).strip()
                ev = m.group(2).strip()
                events.append({"timestamp": ts, "event": ev})
            if events:
                import pandas as pd
                ev_df = pd.DataFrame(events)
                st.dataframe(ev_df, height=180)

            with st.expander("Open full history (read-only)", expanded=False):
                st.text_area("History (copy/paste)", txt, height=320, key=f"hist_txt_{selected_lead_id}")
                st.download_button(
                    "Download history (.md)",
                    txt,
                    file_name=hist_path.name,
                    mime="text/markdown",
                    key=f"hist_dl_{selected_lead_id}",
                )

        st.markdown("---")
        if st.button("Export Lead Pack (.md)", key=f"export_lead_pack_{selected_lead_id}"):
            import subprocess, glob
            cmd = ["uv","run","python","export_lead_pack.py","--lead-id", str(selected_lead_id)]
            r = subprocess.run(cmd, capture_output=True, text=True)
            st.code((r.stdout or "") + (r.stderr or ""), language="text")

            # propose download du dernier pack
            packs = sorted(glob.glob(f"out/lead_pack_{selected_lead_id}_*.md"))
            if packs:
                latest = packs[-1]
                txt_pack = Path(latest).read_text(encoding="utf-8", errors="replace")
                st.download_button(
                    "Download latest Lead Pack (.md)",
                    txt_pack,
                    file_name=Path(latest).name,
                    mime="text/markdown",
                    key=f"dl_lead_pack_{selected_lead_id}",
                )


        st.markdown("---")
        st.subheader("Messages du jour (DeepSeek)")

        # Charge la ligne pipeline correspondant au lead sélectionné
        df_full = load_pipeline()
        df_full["lead_id"] = df_full["lead_id"].astype(str)
        row_df = df_full[df_full["lead_id"] == str(selected_lead_id)]
        if row_df.empty:
            st.warning("Lead introuvable dans pipeline.")
        else:
            row = row_df.iloc[0].to_dict()
            # Auto-mode (robuste) basé sur compute_next_actions (même logique que l’onglet Next Actions)
            try:
                na = compute_next_actions(load_pipeline(), top_k=500, track=(track_filter if track_filter else 'ALL'))
                na['lead_id'] = na['lead_id'].astype(str)
                hit = na[na['lead_id'] == str(selected_lead_id)]
                current_action = str(hit.iloc[0].get('action','')) if not hit.empty else None
            except Exception:
                current_action = None
            
            default_mode = 'FOLLOWUP' if current_action == 'FOLLOWUP_DUE' else 'OUTREACH'

            
            # Persona auto par action (modifiable via UI)
            
            if current_action == 'FOLLOWUP_DUE':
            
                default_persona = 'RELAY'
            
            elif current_action == 'HANDLE_REPLY':
            
                default_persona = 'PEER'
            
            else:
            
                default_persona = 'DECIDER'

            # Cas spécial: HANDLE_REPLY -> on propose un panneau de traitement de réponse
            if current_action == "HANDLE_REPLY":
                st.info("Action = HANDLE_REPLY : colle la réponse reçue, puis génère une réponse + recommandation.")
                inbound = st.text_area("Message reçu (LinkedIn reply)", "", height=140, key=f"inbound_{selected_lead_id}")

                if st.button("Analyze & Draft Reply (FR/EN)", key=f"gen_reply_{selected_lead_id}"):
                    log_event(str(selected_lead_id), "REPLY_RECEIVED", "Inbound LinkedIn reply captured.", {"text": inbound})
                    data = generate_reply_handler_json(row, inbound)
                    log_event(
                        str(selected_lead_id),
                        "REPLY_DRAFTED",
                        "Draft reply generated (FR/EN).",
                        {
                            "analysis_intent": data.get("analysis_intent", ""),
                            "analysis_next_step": data.get("analysis_next_step", ""),
                            "reply_fr": data.get("reply_fr", ""),
                            "reply_en": data.get("reply_en", ""),
                            "recommended_action": data.get("recommended_action", ""),
                        },
                    )
                    st.session_state["reply_last"] = {"lead_id": str(selected_lead_id), "data": data}
                    st.success("OK: reply draft generated.")

                if "reply_last" in st.session_state and st.session_state["reply_last"].get("lead_id") == str(selected_lead_id):
                    data = st.session_state["reply_last"]["data"]
                    st.markdown("#### Analyse")
                    st.write(f"Intent: {data.get('analysis_intent','')}")
                    st.write(f"Next: {data.get('analysis_next_step','')}")
                    st.markdown("#### Draft FR")
                    st.text_area("Réponse FR (copier-coller)", str(data.get("reply_fr","")), height=180, key=f"reply_fr_{selected_lead_id}")
                    st.markdown("#### Draft EN")
                    st.text_area("Reply EN (copy-paste)", str(data.get("reply_en","")), height=180, key=f"reply_en_{selected_lead_id}")

                    rec = str(data.get("recommended_action",""))
                    st.warning(f"Recommended action: {rec}")

                    colA, colB = st.columns([1,1])
                    with colA:
                        if st.button("Apply: Mark REPLIED (stop followups)", key=f"apply_replied_{selected_lead_id}"):
                            # réutilise ton mécanisme existant Mark REPLIED
                            import subprocess
                            subprocess.run(["uv","run","python","mark_replied.py","--lead-id", str(selected_lead_id)], check=False)
                            st.success("Applied: REPLIED")
                            st.rerun()
                    with colB:
                        if st.button("Apply: Mark SENT (J+3)", key=f"apply_sent_{selected_lead_id}"):
                            import subprocess
                            subprocess.run(["uv","run","python","mark_sent.py","--lead-id", str(selected_lead_id)], check=False)
                            st.success("Applied: SENT (J+3)")
                            st.rerun()

                st.markdown("---")

            default_stage = guess_followup_stage(str(selected_lead_id))


            colM1, colM2, colM3 = st.columns([1,1,1])

            with colM1:

                msg_mode = st.selectbox(

                    "Type de message",

                    ["OUTREACH", "FOLLOWUP"],

                    index=0 if default_mode == "OUTREACH" else 1,

                    key=f"msg_mode_{selected_lead_id}",

                )

            with colM2:

                msg_stage = st.selectbox(

                    "Follow-up stage",

                    [1, 2, 3],

                    index=max(0, min(2, int(default_stage) - 1)),

                    key=f"msg_stage_{selected_lead_id}",

                )

            with colM3:

                # init persona par lead si absent (respecte choix utilisateur)

                if f"persona_{selected_lead_id}" not in st.session_state:

                    st.session_state[f"persona_{selected_lead_id}"] = default_persona


                persona = st.selectbox(

                    "Persona",

                    ["DECIDER", "RELAY", "PEER"],

                    index=['DECIDER','RELAY','PEER'].index(st.session_state[f"persona_{selected_lead_id}"]),
                    key=f"persona_{selected_lead_id}",

                    help="DECIDER=Partner/Director/MD | RELAY=Manager/Senior | PEER=Associate/Analyst",

                )


            if msg_mode == "OUTREACH":


                st.markdown("**Quick persona buttons**")


                cQ1, cQ2, cQ3 = st.columns([1,1,1])


                def _run_outreach_for(persona_choice: str) -> None:


                    data = generate_outreach_trackaware(row, persona=persona_choice)

                    st.session_state["outreach_last"] = {
                        "lead_id": str(selected_lead_id),
                        "persona": persona_choice,
                        "data": data,
                    }

                    log_event(
                        str(selected_lead_id),
                        "OUTREACH_GENERATED",
                        "Outreach messages generated (FR/EN x3).",
                        {
                            "mode": "OUTREACH",
                            "persona": persona_choice,
                            "fr_ultra": data.get("fr_ultra",""),
                            "fr_standard": data.get("fr_standard",""),
                            "fr_warm": data.get("fr_warm",""),
                            "en_ultra": data.get("en_ultra",""),
                            "en_standard": data.get("en_standard",""),
                            "en_warm": data.get("en_warm",""),
                        }
                    )

                    st.success(f"OK: messages générés ({persona_choice}).")
                    st.markdown("### Messages (copy/paste)")
                    with st.expander(f"Outreach — {persona_choice} — {selected_lead_id}", expanded=True):
                        st.markdown("#### FR")
                        st.text_area("FR — ULTRA", data.get("fr_ultra",""), height=110, key=f"out_fr_ultra_{selected_lead_id}_{persona_choice}")
                        st.text_area("FR — STANDARD", data.get("fr_standard",""), height=140, key=f"out_fr_standard_{selected_lead_id}_{persona_choice}")
                        st.text_area("FR — WARM", data.get("fr_warm",""), height=170, key=f"out_fr_warm_{selected_lead_id}_{persona_choice}")

                        st.markdown("#### EN")
                        st.text_area("EN — ULTRA", data.get("en_ultra",""), height=110, key=f"out_en_ultra_{selected_lead_id}_{persona_choice}")
                        st.text_area("EN — STANDARD", data.get("en_standard",""), height=140, key=f"out_en_standard_{selected_lead_id}_{persona_choice}")
                        st.text_area("EN — WARM", data.get("en_warm",""), height=170, key=f"out_en_warm_{selected_lead_id}_{persona_choice}")

                        md = f"""# Outreach Pack — {selected_lead_id}
                        Persona: {persona_choice}
                        Track: {row.get('track','')}
                        Contact: {row.get('contact_name','')} — {row.get('title','')} — {row.get('company','')}
                        
---

## FR — ULTRA
{data.get('fr_ultra','')}

## FR — STANDARD
{data.get('fr_standard','')}

## FR — WARM
{data.get('fr_warm','')}

---

## EN — ULTRA
{data.get('en_ultra','')}

## EN — STANDARD
{data.get('en_standard','')}

## EN — WARM
{data.get('en_warm','')}
                        """
                        st.download_button(
                            "Download outreach (.md)",
                            md,
                            file_name=f"outreach_{selected_lead_id}_{persona_choice}.md",
                            mime="text/markdown",
                            key=f"dl_outreach_{selected_lead_id}_{persona_choice}",
                        )
                with cQ1:


                    if st.button("Generate DECIDER", key=f"qa_decider_{selected_lead_id}"):


                        _run_outreach_for("DECIDER")


                with cQ2:


                    if st.button("Generate RELAY", key=f"qa_relay_{selected_lead_id}"):


                        _run_outreach_for("RELAY")


                with cQ3:


                    if st.button("Generate PEER", key=f"qa_peer_{selected_lead_id}"):


                        _run_outreach_for("PEER")



                st.markdown("---")


                # Mode manuel: utilise le persona sélectionné


                if st.button("Generate Outreach Messages (FR/EN x3)", key=f"msg_gen_outreach_{selected_lead_id}"):


                    _run_outreach_for(persona)

            else:

                if st.button("Generate Follow-up Message (FR/EN)", key=f"msg_gen_followup_{selected_lead_id}"):

                    data = generate_followup_json(row, int(msg_stage))

                    log_event(
                        str(selected_lead_id),
                        "FOLLOWUP_GENERATED",
                        "Follow-up message generated (FR/EN).",
                        {
                            "mode": "FOLLOWUP",
                            "stage": int(msg_stage),
                            "fr": data.get("fr", ""),
                            "en": data.get("en", ""),
                        },
                    )

                    st.success("OK: follow-up généré.")

                    st.markdown("### FR")

                    st.text(data.get("fr",""))

                    st.markdown("### EN")

                    st.text(data.get("en",""))

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            if st.button("Mark SENT (J+3)", key="na_mark_sent"):
                cmd = ["uv", "run", "python", "mark_sent.py", "--lead-id", selected_lead_id]
                code, out = run_cmd(cmd)
                st.code(out, language="text")

        with c2:
            if st.button("Force followup TODAY", key="na_force_today"):
                cmd = ["uv", "run", "python", "set_followup_today.py", "--lead-id", selected_lead_id]
                code, out = run_cmd(cmd)
                st.code(out, language="text")

        with c3:
            if st.button("Mark REPLIED", key="na_mark_replied"):
                cmd = ["uv", "run", "python", "mark_replied.py", "--lead-id", selected_lead_id, "--details", "Reply via NextActions UI"]
                code, out = run_cmd(cmd)
                st.code(out, language="text")

        with c4:
            if st.button("Generate Followups Pack", key="na_gen_followups"):
                cmd = ["uv", "run", "--env-file", ".env", "python", "generate_followups.py", "--top", str(top_k)]
                code, out = run_cmd(cmd)
                st.code(out, language="text")

    st.caption("Toujours human-in-the-loop: l'UI prépare et met à jour le pipeline, Maeva envoie sur LinkedIn manuellement.")

with tab4:
    st.subheader("4) Packs & Follow-ups")

    colL, colR = st.columns([1, 1])

    with colL:
        st.markdown("### Générer un pack de prospection (Outreach)")

        # Choix du fichier inbox (data/inbox) ou sample (samples/)
        inbox_dir = Path("data/inbox")
        sample_dir = Path("samples")
        inbox_dir.mkdir(parents=True, exist_ok=True)
        sample_dir.mkdir(parents=True, exist_ok=True)

        candidates = []
        candidates += sorted([str(x) for x in inbox_dir.glob("*.csv")])
        candidates += sorted([str(x) for x in sample_dir.glob("*.csv")])

        if not candidates:
            st.warning("Aucun CSV trouvé dans data/inbox/ ou samples/. Ajoute un CSV puis recharge.")
            selected_csv = "samples/leads_sample.csv"
        else:
            selected_csv = st.selectbox(
                "Fichier leads (CSV) utilisé pour générer le pack",
                candidates,
                index=0,
                key="pack_csv_selector"
            )


        if st.button("Generate Outreach Pack (Top K)", type="primary"):
            cmd = ["uv", "run", "--env-file", ".env", "python", "run_weekly_pack.py",
                   "--input", "samples/leads_sample.csv", "--top", str(top_k)]
            code, out = run_cmd(cmd)
            if code == 0:
                st.success("Pack généré. Voir dossier out/.")
                st.code(out, language="text")
            else:
                st.error(out)

        st.markdown("---")
        st.markdown("### Générer un pack de relances (Follow-ups)")
        st.write("Produit: `out/followups_pack_YYYYMMDD.md`")

        if st.button("Generate Followups Pack (Due)", type="primary"):
            cmd = ["uv", "run", "--env-file", ".env", "python", "generate_followups.py", "--top", str(top_k)]
            code, out = run_cmd(cmd)
            if code == 0:
                st.success("Followups pack généré (si des relances sont dues).")
                st.code(out, language="text")
            else:
                st.error(out)

    with colR:
        st.markdown("### Actions statut (Mark Sent / Replied / Followup Sent)")
        st.write("Saisis un `lead_id` depuis le pipeline (onglet Pipeline).")

        # Lead picker (évite la saisie manuelle)
        df_pick = refresh_pipeline()
        df_pick = df_pick.sort_values(by=["priority","score"], ascending=[True, False])

        options = []
        mapping = {}
        for _, r in df_pick.iterrows():
            lid = str(r["lead_id"])
            label = f'{lid} | {r["contact_name"]} | {r["company"]} | {r["title"]} | {r["track"]} | {r["status"]} | prio={r["priority"]} | score={r["score"]}'
            options.append(label)
            mapping[label] = lid

        if options:
            selected_label = st.selectbox("Choisir un lead", options, index=0, key="lead_picker")
            lead_id = mapping[selected_label]
        else:
            st.warning("Pipeline vide: importe des leads dans Inbox Import.")
            lead_id = ""
        stage = st.selectbox("Followup stage (pour mark_followup_sent)", [1, 2, 3], index=0)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Mark SENT (planifier J+3)"):
                if not lead_id.strip():
                    st.warning("lead_id requis.")
                else:
                    cmd = ["uv", "run", "python", "mark_sent.py", "--lead-id", lead_id.strip()]
                    code, out = run_cmd(cmd)
                    st.code(out, language="text")

            if st.button("Force followup TODAY (test)"):
                if not lead_id.strip():
                    st.warning("lead_id requis.")
                else:
                    cmd = ["uv", "run", "python", "set_followup_today.py", "--lead-id", lead_id.strip()]
                    code, out = run_cmd(cmd)
                    st.code(out, language="text")

        with c2:
            if st.button("Mark REPLIED (stop followups)"):
                if not lead_id.strip():
                    st.warning("lead_id requis.")
                else:
                    cmd = ["uv", "run", "python", "mark_replied.py", "--lead-id", lead_id.strip(), "--details", "Reply via UI"]
                    code, out = run_cmd(cmd)
                    st.code(out, language="text")

            if st.button("Mark FOLLOWUP SENT"):
                if not lead_id.strip():
                    st.warning("lead_id requis.")
                else:
                    cmd = ["uv", "run", "python", "mark_followup_sent.py", "--lead-id", lead_id.strip(), "--stage", str(stage)]
                    code, out = run_cmd(cmd)
                    st.code(out, language="text")

    st.markdown("---")
    st.subheader("Derniers fichiers générés (out/)")
    files = sorted(OUT_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        st.info("Aucun fichier dans out/ pour l’instant.")
    else:
        for f in files[:10]:
            with st.expander(f.name):
                st.text(f.read_text(encoding="utf-8", errors="replace")[:5000])
