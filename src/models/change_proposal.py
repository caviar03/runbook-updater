from pydantic import BaseModel


class proposedChange(BaseModel):
    runbook: str
    section: str
    current_text: str
    proposed_text: str
    reason: str


class changeProposal(BaseModel):
    changes: list[proposedChange]
    readable_feedback: str
