from typing import Optional
from pydantic import BaseModel


class proposedChange(BaseModel):
    section: str
    current_text: str
    proposed_text: str
    reason: str


class changeProposal(BaseModel):
    changes: list[proposedChange]
    readable_feedback: str
    approved_changes: Optional["changeProposal"] = None