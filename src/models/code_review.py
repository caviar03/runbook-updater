from pydantic import BaseModel


class CodeChange(BaseModel):
    description: str
    affected_components: list[str]
    operational_impact: str
    runbook_relevant: bool


class Discrepancy(BaseModel):
    code_behavior: str
    runbook_claim: str
    explanation: str
    severity: str


class CodeChangeReview(BaseModel):
    code_changes: list[CodeChange]
    existing_discrepancies: list[Discrepancy]