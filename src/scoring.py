import re
import pandas as pd

# Heuristiques simples, transparentes (pas de magie)
SENIORITY = [
    ("partner", 25), ("director", 20), ("md", 20), ("managing director", 20),
    ("senior manager", 18), ("manager", 15),
    ("associate", 12), ("analyst", 10), ("senior", 10),
]

TRACK_KEYWORDS = {
    "MA": ["m&a", "mergers", "acquisitions", "corporate finance", "investment banking", "ibd", "deal"],
    "TS": ["transaction services", "deal advisory", "valuation", "fdd", "financial due diligence"],
    "TT": ["transaction tax", "tax", "m&a tax", "structuring", "international tax"],
}

PARIS_MATCH = ["paris", "île-de-france", "ile-de-france"]


def _contains_any(text: str, words: list[str]) -> bool:
    t = (text or "").lower()
    return any(w in t for w in words)


def score_row(row) -> int:
    title = str(row.get("title",""))
    company = str(row.get("company",""))
    location = str(row.get("location",""))

    score = 0

    # 1) Track fit
    track = row.get("track","MA")
    kws = TRACK_KEYWORDS.get(track, [])
    if _contains_any(title, kws) or _contains_any(company, kws):
        score += 25
    else:
        score += 10  # on ne met pas 0 : parfois les titres sont ambigus

    # 2) Seniority
    t = title.lower()
    for k, pts in SENIORITY:
        if k in t:
            score += pts
            break

    # 3) Location (Paris/IDF)
    if _contains_any(location, PARIS_MATCH):
        score += 10

    # 4) Bonus: Big4 / PE / Bank (simple signaux)
    comp = company.lower()
    if any(x in comp for x in ["deloitte","ey","kpmg","pwc"]):
        score += 6
    if any(x in comp for x in ["capital","partners","private equity","investment"]):
        score += 6
    if any(x in comp for x in ["bnp","societe generale","goldman","jpmorgan","rothschild","lazard"]):
        score += 6

    return int(min(score, 100))


def apply_scoring(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["score"] = df.apply(score_row, axis=1)

    def prio(s: int) -> str:
        if s >= 70: return "A"
        if s >= 50: return "B"
        return "C"

    df["priority"] = df["score"].apply(prio)
    return df
