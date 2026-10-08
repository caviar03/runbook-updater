from pydantic import BaseModel


class runbookIssue(BaseModel):
    runbook: str = ""
    section: str
    issue: str
    evidence_from_code: str
    recommended_change: str
    priority: str


class runbookReview(BaseModel):
    update_required: bool
    issues: list[runbookIssue]