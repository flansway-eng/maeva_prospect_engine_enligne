from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

BASE_DIR = Path("data/conversations")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_dir() -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)


def _truncate(txt: str, n: int = 260) -> str:
    txt = (txt or "").strip()
    return txt if len(txt) <= n else (txt[:n] + "…")


def _json_default(o: Any) -> Any:
    # numpy scalars -> python scalars
    try:
        import numpy as np  # optional
        if isinstance(o, (np.integer, np.floating)):
            return o.item()
    except Exception:
        pass

    # pandas Timestamp -> isoformat
    try:
        import pandas as pd  # optional
        if isinstance(o, pd.Timestamp):
            return o.isoformat()
    except Exception:
        pass

    # Path -> str
    if isinstance(o, Path):
        return str(o)

    # set/tuple -> list
    if isinstance(o, (set, tuple)):
        return list(o)

    # fallback
    return str(o)


def _payload_summary(payload: Dict[str, Any]) -> list[str]:
    """
    Résumé humain stable: - `key`: value (tronqué)
    """
    if not isinstance(payload, dict) or not payload:
        return []
    out: list[str] = []
    for k in sorted(payload.keys()):
        v = payload.get(k)
        if v is None:
            continue

        if isinstance(v, str):
            vv = _truncate(v, 260).replace("\n", " ").strip()
        elif isinstance(v, (int, float, bool)):
            vv = str(v)
        elif isinstance(v, list):
            vv = f"list(len={len(v)})"
        elif isinstance(v, dict):
            vv = f"dict(keys={len(v)})"
        else:
            vv = _truncate(str(v), 180)

        out.append(f"- `{k}`: {vv}")
    return out


def log_event(
    lead_id: str,
    event: str,
    summary: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Sprint 3.9 — Dual Log (append-only):
    1) Payload (résumé) : lisible humain
    2) Payload (raw JSON) : machine-readable (bloc ```json)
    Fichier: data/conversations/<lead_id>.md
    """
    import json

    ensure_dir()

    lead_id = str(lead_id).strip()
    if not lead_id:
        # on ne loggue rien si lead_id vide
        return BASE_DIR / "_invalid_.md"

    hist_path = BASE_DIR / f"{lead_id}.md"

    event = (event or "EVENT").strip()
    summary = (summary or "").strip()

    if payload is None:
        payload = {}
    elif not isinstance(payload, dict):
        payload = {"value": payload}

    bullets = _payload_summary(payload)
    raw_json = json.dumps(
        payload,
        indent=2,
        ensure_ascii=False,
        sort_keys=True,
        default=_json_default,
    )

    lines: list[str] = []
    lines.append(f"## {_now()} — {event}\n")
    lines.append((summary + "\n\n") if summary else "\n")

    lines.append("**Payload (résumé):**\n\n")
    if bullets:
        lines.append("\n".join(bullets) + "\n\n")
    else:
        lines.append("- (vide)\n\n")

    lines.append("**Payload (raw JSON):**\n\n")
    lines.append("```json\n")
    lines.append(raw_json + "\n")
    lines.append("```\n\n")

    existing = hist_path.read_text(encoding="utf-8") if hist_path.exists() else ""
    hist_path.write_text(existing + "".join(lines), encoding="utf-8")
    return hist_path
