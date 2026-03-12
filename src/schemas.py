from pydantic import BaseModel, Field
from typing import Optional, Literal, List


Track = Literal["MA", "TS", "TT"]  # M&A, Transaction Services, Transaction Tax


class Lead(BaseModel):
    track: Track
    company: str
    contact_name: str
    title: str
    linkedin_url: str
    location: str = "Paris"
    source: str = "LinkedIn"
    notes: Optional[str] = ""


class PipelineRow(Lead):
    lead_id: str
    score: int = 0
    priority: Literal["A", "B", "C"] = "B"
    status: Literal["NEW", "DRAFT_READY", "SENT", "REPLIED", "CALL", "INTERVIEW", "CLOSED"] = "NEW"
    last_action: Optional[str] = ""
    next_followup: Optional[str] = ""  # ISO date string


class MessagePack(BaseModel):
    lead_id: str
    contact_name: str
    company: str
    title: str
    track: Track
    persona: Literal["DECIDER", "RELAY", "PEER"]
    language: Literal["FR", "EN"]
    message: str = Field(..., min_length=1)


class OutreachPack(BaseModel):
    week: str
    top_k: int
    items: List[MessagePack]
